"""
Wine vintage data builder for loading and managing vintage entries.
"""
import pandas as pd
import re
import random
from pathlib import Path
from typing import List
from src.vintage_models import WineVintage, validate_vintage
from src.pinecone_client import get_index


class VintageBuilder:
    """Manages wine vintage entries and Pinecone uploads."""
    
    def __init__(self):
        self.entries: List[WineVintage] = []
        self.output_dir = Path("data")
        self.output_dir.mkdir(exist_ok=True)
    
    def add_entry(self, entry: WineVintage):
        """Add a vintage entry after validation."""
        if not validate_vintage(entry):
            raise ValueError(f"Invalid vintage entry: {entry}")
        self.entries.append(entry)
    
    def load_from_excel(self, file_path: str):
        """Load vintage entries from Excel file with region columns."""
        df = pd.read_excel(file_path, header=None)
        
        # First row contains region names, second row contains column headers
        # Process each pair of columns (region, rating & notes)
        num_regions = df.shape[1] // 2
        
        for i in range(num_regions):
            col_idx = i * 2
            region_name = df.iloc[0, col_idx]
            
            # Skip if region name is NaN or empty
            if pd.isna(region_name) or str(region_name).strip() == '':
                continue
            
            # Process vintages starting from row 2 (index 2)
            for row_idx in range(2, len(df)):
                vintage_year = df.iloc[row_idx, col_idx]
                rating_notes = df.iloc[row_idx, col_idx + 1]
                
                # Skip if vintage or notes are missing
                if pd.isna(vintage_year) or pd.isna(rating_notes):
                    continue
                
                # Try to convert vintage to int
                try:
                    vintage_year = int(vintage_year)
                except (ValueError, TypeError):
                    continue
                
                # Parse rating from notes (format: "90: Some notes...")
                rating = None
                notes = str(rating_notes).strip()
                
                # Extract rating if present (number followed by colon)
                rating_match = re.match(r'^(\d+):\s*(.+)$', notes)
                if rating_match:
                    rating = int(rating_match.group(1))
                    notes = rating_match.group(2).strip()
                
                entry = WineVintage(
                    region=str(region_name).strip(),
                    vintage=vintage_year,
                    rating=rating,
                    notes=notes
                )
                
                self.add_entry(entry)
    
    def save_as_jsonl(self, file_name: str = "wine_vintages.jsonl"):
        """Save entries as JSON Lines."""
        output_path = self.output_dir / file_name
        with open(output_path, 'w', encoding='utf-8') as f:
            for entry in self.entries:
                f.write(entry.to_json() + '\n')
        print(f"Saved {len(self.entries)} vintage entries to {output_path}")
    
    def save_as_csv(self, file_name: str = "wine_vintages.csv"):
        """Save entries as CSV."""
        output_path = self.output_dir / file_name
        df = pd.DataFrame([e.to_dict() for e in self.entries])
        df.to_csv(output_path, index=False)
        print(f"Saved {len(self.entries)} vintage entries to {output_path}")
    
    def push_to_pinecone(self, namespace: str = "vintages"):
        """Push all entries to Pinecone."""
        if not self.entries:
            print("No entries to push")
            return
        
        index = get_index()
        
        # Prepare vectors with metadata
        vectors = []
        for i, entry in enumerate(self.entries):
            # Create unique ID: region_vintage
            region_key = entry.region.replace(' ', '_').replace('(', '').replace(')', '').replace(',', '')
            vector_id = f"{region_key}_{entry.vintage}"
            
            # Use placeholder embeddings (1024 dimensions with small random values)
            # In production, you'd generate real embeddings from notes
            embedding = [random.uniform(0.001, 0.01) for _ in range(1024)]
            
            metadata = entry.to_dict()
            # Remove None values from metadata (Pinecone doesn't accept null)
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            vectors.append({
                'id': vector_id,
                'values': embedding,
                'metadata': metadata
            })
        
        # Upload in batches of 100
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(vectors=batch, namespace=namespace)
        
        print(f"Pushed {len(vectors)} vintage entries to Pinecone namespace '{namespace}'")
    
    def get_stats(self):
        """Get statistics about loaded entries."""
        if not self.entries:
            return {"count": 0}
        
        regions = set(e.region for e in self.entries)
        vintages = set(e.vintage for e in self.entries)
        with_ratings = sum(1 for e in self.entries if e.rating is not None)
        
        return {
            "count": len(self.entries),
            "regions": len(regions),
            "region_names": sorted(regions),
            "vintage_range": (min(vintages), max(vintages)),
            "entries_with_ratings": with_ratings
        }
