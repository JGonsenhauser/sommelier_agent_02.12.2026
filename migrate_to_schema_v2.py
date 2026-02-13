"""
Migration script to update Pinecone vectors to Schema V2.

This script:
1. Reads existing wine data from CSV/Excel
2. Transforms to new standardized schema
3. Generates new vector IDs (master hash format)
4. Creates standardized text field (no price/restaurant)
5. Re-embeds to Pinecone with new metadata structure
"""
import sys
from pathlib import Path
import logging
import pandas as pd
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

from data.schema_v2 import (
    CoreWineMetadata,
    RestaurantWineMetadata,
    get_price_range
)
from data.embedding_pipeline import EmbeddingPipeline
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchemaV2Migrator:
    """Migrates wine data to Schema V2 format."""

    def __init__(self):
        self.pipeline = EmbeddingPipeline()

    def load_wine_data(self, file_path: Path) -> pd.DataFrame:
        """Load wine data from CSV or Excel."""
        if file_path.suffix.lower() in {'.xlsx', '.xls'}:
            df = pd.read_excel(file_path)
        elif file_path.suffix.lower() == '.csv':
            df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")

        logger.info(f"Loaded {len(df)} wines from {file_path}")
        return df

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to match Schema V2."""
        # Map old column names to new schema
        column_mapping = {
            'Producer': 'producer',
            'Label': 'label',
            'Grapes': 'grapes',
            'Region': 'region',
            'Major Region': 'major_region',
            'Country': 'country',
            'wine_name': 'label',  # Old schema compatibility
            'vintage': 'vintage',
            'price': 'price',
            'wine_type': 'wine_type',
            'tasting_note': 'tasting_keywords'
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Fill missing optional fields
        if 'label' not in df.columns:
            df['label'] = ''
        if 'major_region' not in df.columns:
            df['major_region'] = df['region']
        if 'vintage' not in df.columns:
            df['vintage'] = ''
        if 'wine_type' not in df.columns:
            df['wine_type'] = ''
        if 'tasting_keywords' not in df.columns:
            df['tasting_keywords'] = ''

        # Fill NaN values
        df = df.fillna('')

        return df

    def transform_to_schema_v2(
        self,
        df: pd.DataFrame,
        restaurant: str,
        list_id: str,
        qr_id: str
    ) -> List[Dict]:
        """Transform DataFrame to Schema V2 format."""
        wines = []

        for idx, row in df.iterrows():
            # Generate standardized text (no price, no restaurant)
            text = CoreWineMetadata.generate_text(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                major_region=str(row.get('major_region', row['region'])),
                country=str(row['country'])
            )

            # Generate master ID
            master_id = CoreWineMetadata.generate_master_id(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                country=str(row['country'])
            )

            # Get price and price range
            price = None
            price_range = ""
            if 'price' in row and pd.notna(row['price']):
                try:
                    price = float(row['price'])
                    price_range = get_price_range(price)
                except:
                    price_range = "<$50"  # Default if price invalid
            else:
                price_range = "<$50"  # Default if no price

            # Create restaurant metadata
            wine_metadata = RestaurantWineMetadata(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                major_region=str(row.get('major_region', row['region'])),
                country=str(row['country']),
                text=text,
                price_range=price_range,
                price=price,
                list_id=list_id,
                qr_id=qr_id,
                restaurant=restaurant,
                tasting_keywords=str(row.get('tasting_keywords', '')),
                vintage=str(row.get('vintage', '')),
                wine_type=str(row.get('wine_type', ''))
            )

            # Generate restaurant-specific vector ID
            restaurant_vector_id = RestaurantWineMetadata.generate_restaurant_id(
                restaurant=restaurant,
                list_id=list_id,
                qr_id=qr_id,
                master_id=master_id
            )

            wines.append({
                'master_id': master_id,
                'restaurant_vector_id': restaurant_vector_id,
                'text': text,
                'metadata': wine_metadata.to_dict()
            })

        logger.info(f"Transformed {len(wines)} wines to Schema V2")
        return wines

    def embed_to_pinecone(
        self,
        wines: List[Dict],
        namespace: str,
        batch_size: int = 100
    ) -> int:
        """Embed wines to Pinecone with new schema."""
        logger.info(f"Embedding {len(wines)} wines to namespace: {namespace}")

        # Generate embeddings for all texts
        texts = [wine['text'] for wine in wines]
        embeddings = self.pipeline.get_embeddings(texts)

        # Build vectors
        vectors = []
        for wine, embedding in zip(wines, embeddings):
            vectors.append({
                'id': wine['restaurant_vector_id'],
                'values': embedding,
                'metadata': wine['metadata']
            })

        # Upload in batches
        total_uploaded = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                self.pipeline.index.upsert(vectors=batch, namespace=namespace)
                total_uploaded += len(batch)
                logger.info(f"Uploaded batch {i//batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                logger.error(f"Error uploading batch: {e}")

        logger.info(f"Successfully uploaded {total_uploaded} vectors to {namespace}")
        return total_uploaded

    def migrate_restaurant_list(
        self,
        file_path: Path,
        restaurant: str,
        list_id: str,
        namespace: str
    ) -> int:
        """Migrate a complete restaurant wine list."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating {restaurant} wine list to Schema V2")
        logger.info(f"{'='*60}")

        # Load data
        df = self.load_wine_data(file_path)

        # Normalize column names
        df = self.normalize_dataframe(df)

        # Validate required fields
        required = ['producer', 'grapes', 'region', 'country']
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Transform to Schema V2
        qr_id = f"qr_{restaurant}"
        wines = self.transform_to_schema_v2(
            df=df,
            restaurant=restaurant,
            list_id=list_id,
            qr_id=qr_id
        )

        # Embed to Pinecone
        embedded_count = self.embed_to_pinecone(
            wines=wines,
            namespace=namespace
        )

        logger.info(f"\n{'='*60}")
        logger.info(f"Migration complete: {embedded_count} wines embedded")
        logger.info(f"Namespace: {namespace}")
        logger.info(f"{'='*60}\n")

        return embedded_count

    def migrate_producers_list(
        self,
        file_path: Path,
        namespace: str = "producers"
    ) -> int:
        """Migrate producers list with master IDs."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Migrating producers list to Schema V2")
        logger.info(f"{'='*60}")

        # Load data
        df = self.load_wine_data(file_path)

        # Normalize column names
        df = self.normalize_dataframe(df)

        # Transform to master format (no restaurant-specific fields)
        wines = []
        for idx, row in df.iterrows():
            text = CoreWineMetadata.generate_text(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                major_region=str(row.get('major_region', row['region'])),
                country=str(row['country'])
            )

            master_id = CoreWineMetadata.generate_master_id(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                country=str(row['country'])
            )

            # Core metadata only (no restaurant fields)
            core_metadata = CoreWineMetadata(
                producer=str(row['producer']),
                label=str(row.get('label', '')),
                grapes=str(row['grapes']),
                region=str(row['region']),
                major_region=str(row.get('major_region', row['region'])),
                country=str(row['country']),
                text=text
            )

            # Add optional tasting note if present
            metadata_dict = core_metadata.to_dict()
            if 'tasting_keywords' in row and pd.notna(row['tasting_keywords']):
                metadata_dict['tasting_note'] = str(row['tasting_keywords'])

            wines.append({
                'master_id': master_id,
                'text': text,
                'metadata': metadata_dict
            })

        # Generate embeddings
        texts = [wine['text'] for wine in wines]
        embeddings = self.pipeline.get_embeddings(texts)

        # Build vectors with master IDs
        vectors = []
        for wine, embedding in zip(wines, embeddings):
            vectors.append({
                'id': wine['master_id'],  # Use master hash as ID
                'values': embedding,
                'metadata': wine['metadata']
            })

        # Upload to Pinecone
        total_uploaded = 0
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                self.pipeline.index.upsert(vectors=batch, namespace=namespace)
                total_uploaded += len(batch)
                logger.info(f"Uploaded batch {i//batch_size + 1}: {len(batch)} vectors")
            except Exception as e:
                logger.error(f"Error uploading batch: {e}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Producers migration complete: {total_uploaded} wines")
        logger.info(f"{'='*60}\n")

        return total_uploaded


def main():
    """Main migration script."""
    print("\n" + "="*60)
    print("Schema V2 Migration Tool")
    print("="*60 + "\n")

    migrator = SchemaV2Migrator()

    # Migrate MAASS restaurant list
    maass_file = Path("MAASS_Wine_List.xlsx")
    if maass_file.exists():
        print("[1/2] Migrating MAASS wine list...")
        try:
            count = migrator.migrate_restaurant_list(
                file_path=maass_file,
                restaurant="maass",
                list_id="maass_wine_list",
                namespace="maass_wine_list"
            )
            print(f"[OK] MAASS: {count} wines migrated\n")
        except Exception as e:
            print(f"[ERROR] MAASS migration failed: {e}\n")
            logger.exception("MAASS migration error")
    else:
        print("[SKIP] MAASS_Wine_List.xlsx not found\n")

    # Migrate producers list (if available)
    producers_file = Path("producer_list_organized.xlsx")
    if producers_file.exists():
        print("[2/2] Migrating producers list...")
        try:
            count = migrator.migrate_producers_list(
                file_path=producers_file,
                namespace="producers"
            )
            print(f"[OK] Producers: {count} wines migrated\n")
        except Exception as e:
            print(f"[ERROR] Producers migration failed: {e}\n")
            logger.exception("Producers migration error")
    else:
        print("[SKIP] producer_list_organized.xlsx not found\n")

    print("="*60)
    print("Migration Complete!")
    print("="*60)
    print("\nNew Schema Features:")
    print("- Standardized text field (no price/restaurant)")
    print("- Master hash IDs (deterministic)")
    print("- Restaurant IDs ({restaurant}_{list_id}_{qr_id}_wine_{hash})")
    print("- Core + restaurant-specific metadata separation")
    print("- sync_version = 2")
    print("\nNext steps:")
    print("1. Test search with new schema")
    print("2. Update recommender to use new field names")
    print("3. Verify vector IDs are correct")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
