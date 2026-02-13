"""
Main orchestrator for wine taxonomy building and Pinecone storage.
"""
import json
import csv
from pathlib import Path
from typing import List
import pandas as pd

from src.models import WineTaxonomy, validate_taxonomy
from src.pinecone_client import get_index


class TaxonomyBuilder:
    """Build and manage wine region taxonomy."""
    
    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.entries: List[WineTaxonomy] = []
    
    def add_entry(self, entry: WineTaxonomy):
        """Add validated entry to taxonomy."""
        if validate_taxonomy(entry):
            self.entries.append(entry)
        else:
            raise ValueError(f"Invalid taxonomy entry: {entry}")
    
    def load_from_json_lines(self, file_path: str):
        """Load entries from JSONL file."""
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    entry = WineTaxonomy.from_dict(data)
                    self.add_entry(entry)
    
    def load_from_csv(self, file_path: str):
        """Load entries from CSV file."""
        df = pd.read_csv(file_path)
        for _, row in df.iterrows():
            # Skip rows with missing required fields
            if pd.isna(row.get('world_type')) or pd.isna(row.get('country')) or pd.isna(row.get('region')):
                continue
                
            # Convert common_blends from string to list
            blends = row['common_blends']
            if pd.isna(blends) or blends == '':
                blends = []
            elif isinstance(blends, str):
                blends = [b.strip() for b in blends.split(',')]
            else:
                blends = []
            
            # Handle optional fields - convert NaN/empty to None
            larger_region = row.get('larger_region')
            if pd.isna(larger_region) or larger_region == '':
                larger_region = None
            
            sub_region = row.get('sub_region')
            if pd.isna(sub_region) or sub_region == '':
                sub_region = None
            
            entry = WineTaxonomy(
                world_type=row['world_type'],
                country=row['country'],
                region=row['region'],
                sub_region=sub_region,
                larger_region=larger_region,
                wine_type=row['wine_type'],
                primary_grape=row['primary_grape'],
                common_blends=blends,
                typical_styles=row['typical_styles'],
                food_pairings=row['food_pairings'],
                source_url=row.get('source_url', None)
            )
            self.add_entry(entry)
    
    def save_as_jsonl(self, file_name: str = "wine_taxonomy.jsonl"):
        """Save entries as JSON Lines."""
        output_path = self.output_dir / file_name
        with open(output_path, 'w') as f:
            for entry in self.entries:
                f.write(entry.to_json() + '\n')
        return output_path
    
    def save_as_csv(self, file_name: str = "wine_taxonomy.csv"):
        """Save entries as CSV."""
        output_path = self.output_dir / file_name
        df = pd.DataFrame([e.to_dict() for e in self.entries])
        df.to_csv(output_path, index=False)
        return output_path
    
    def push_to_pinecone(self, namespace: str = "taxonomy"):
        """Push all entries to Pinecone with metadata."""
        index = get_index()
        vectors = []
        
        for i, entry in enumerate(self.entries):
            # Create ASCII-safe vector ID (remove accents/special chars)
            import unicodedata
            region_clean = unicodedata.normalize('NFKD', entry.region).encode('ASCII', 'ignore').decode('ASCII')
            country_clean = unicodedata.normalize('NFKD', entry.country).encode('ASCII', 'ignore').decode('ASCII')
            vector_id = f"{country_clean}_{region_clean}_{i}".replace(' ', '_')
            
            # Store metadata (filter out None values - Pinecone doesn't accept null)
            metadata = {k: v for k, v in entry.to_dict().items() if v is not None}
            metadata['region_key'] = f"{entry.country}/{entry.region}"
            
            # Placeholder: simple non-zero embedding (Pinecone requires non-zero values)
            # Replace with actual OpenAI/Cohere embeddings later
            embedding = [0.01] * 1024
            
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            })
        
        # Upsert to Pinecone
        index.upsert(vectors=vectors, namespace=namespace)
        print(f"Pushed {len(vectors)} entries to Pinecone namespace '{namespace}'")
    
    def get_stats(self):
        """Get taxonomy statistics."""
        return {
            "total_entries": len(self.entries),
            "countries": len(set(e.country for e in self.entries)),
            "regions": len(set(e.region for e in self.entries)),
            "world_types": set(e.world_type for e in self.entries)
        }


if __name__ == "__main__":
    # Example usage
    builder = TaxonomyBuilder()
    
    # Create sample entry
    entry = WineTaxonomy(
        world_type="old",
        country="Italy",
        region="Chianti Classico",
        larger_region="Tuscany",
        primary_grape="Sangiovese",
        common_blends=["Canaiolo", "Colorino"],
        typical_styles="medium-bodied, high acidity, cherry, herbs",
        food_pairings="tomato-based pasta, grilled meats",
        source_url="https://winefolly.com/..."
    )
    
    builder.add_entry(entry)
    print(builder.get_stats())
