"""
Embed schema-compliant MAASS wine list to Pinecone with proper metadata.
Uses the new unified schema with master + restaurant namespaces.
"""
import pandas as pd
import hashlib
from pathlib import Path
from data.embedding_pipeline import EmbeddingPipeline
from data.schema_definitions import RestaurantWineEmbedding
from config import settings

def generate_master_vector_id(producer, label, grapes, region, country):
    """Generate deterministic master vector ID (MD5 hash)."""
    text = f"{producer}_{label or ''}_{grapes}_{region}_{country}"
    return hashlib.md5(text.encode()).hexdigest()

def embed_schema_compliant_maass():
    """Embed schema-compliant MAASS wine list to Pinecone."""
    print("\n" + "="*80)
    print("EMBEDDING SCHEMA-COMPLIANT MAASS WINE LIST TO PINECONE")
    print("="*80)
    
    # Read compliant CSV
    csv_path = Path('data/raw/maass_wine_list_schema_compliant.csv')
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found. Run fix_schema_compliance.py first.")
    
    df = pd.read_csv(csv_path)
    print(f"\n✓ Loaded {len(df)} wines from {csv_path}")
    print(f"  Columns: {list(df.columns)}")
    
    # Initialize pipeline
    pipeline = EmbeddingPipeline()
    
    # Process in batches
    batch_size = 100
    vectors_master = []
    vectors_restaurant = []
    
    print(f"\n📝 Preparing {len(df)} wines for embedding...")
    
    for idx, row in df.iterrows():
        # Generate master vector ID (deterministic)
        master_id = generate_master_vector_id(
            row['producer'],
            row.get('label', ''),
            row['grapes'],
            row['region'],
            row['country']
        )
        
        # Get embedding for the text field
        embedding = pipeline.get_embeddings([row['text']])[0]
        
        # ===== MASTER NAMESPACE (core metadata only) =====
        master_vector = {
            "id": master_id,
            "values": embedding,
            "metadata": {
                "producer": row['producer'],
                "label": row.get('label', ''),
                "grapes": row['grapes'],
                "region": row['region'],
                "major_region": row.get('major_region', row['region']),
                "country": row['country'],
                "text": row['text'],
                "sync_version": 1,
                "source": "maass_schema_v2"
            }
        }
        vectors_master.append(master_vector)
        
        # ===== RESTAURANT NAMESPACE (with restaurant-specific fields) =====
        restaurant_vector_id = f"maass_{row['list_id']}_wine_{master_id[:8]}"
        restaurant_vector = {
            "id": restaurant_vector_id,
            "values": embedding,
            "metadata": {
                # Core
                "producer": row['producer'],
                "label": row.get('label', ''),
                "grapes": row['grapes'],
                "region": row['region'],
                "major_region": row.get('major_region', row['region']),
                "country": row['country'],
                "text": row['text'],
                "sync_version": 1,
                # Restaurant-specific
                "price_range": row['price_range'],
                "price": row.get('price'),
                "tasting_keywords": row['tasting_keywords'],
                "list_id": row['list_id'],
                "qr_id": row['qr_id'],
                "restaurant": row['restaurant'],
                "source": "maass_schema_v2"
            }
        }
        vectors_restaurant.append(restaurant_vector)
        
        if (idx + 1) % 50 == 0 or (idx + 1) == len(df):
            print(f"  Prepared {idx + 1}/{len(df)} wines")
    
    # Upsert to Pinecone
    print(f"\n🔼 Upserting to Pinecone index 'wineregionscrape'...")
    
    try:
        # Clear old namespaces first
        print("  Clearing old 'maass_wine_list' namespace...")
        pipeline.index.delete(delete_all=True, namespace='maass_wine_list')
        print("  Clearing old 'master' namespace (MAASS only)...")
        pipeline.index.delete(filter={"source": "maass_schema_v2"}, namespace='master')
    except Exception as e:
        print(f"  Note: {e}")
    
    # Upsert master vectors
    print(f"\n  Upserting {len(vectors_master)} master vectors...")
    for i in range(0, len(vectors_master), batch_size):
        batch = vectors_master[i:i+batch_size]
        pipeline.index.upsert(vectors=batch, namespace='master')
        print(f"    ✓ Master batch {i//batch_size + 1}/{(len(vectors_master)-1)//batch_size + 1}")
    
    # Upsert restaurant vectors
    print(f"\n  Upserting {len(vectors_restaurant)} restaurant vectors...")
    for i in range(0, len(vectors_restaurant), batch_size):
        batch = vectors_restaurant[i:i+batch_size]
        pipeline.index.upsert(vectors=batch, namespace='maass_wine_list')
        print(f"    ✓ Restaurant batch {i//batch_size + 1}/{(len(vectors_restaurant)-1)//batch_size + 1}")
    
    # Verify
    print(f"\n✅ EMBEDDING COMPLETE!")
    print(f"   Master namespace: {len(vectors_master)} vectors")
    print(f"   maass_wine_list restaurant namespace: {len(vectors_restaurant)} vectors")
    print(f"   Index: wineregionscrape")
    print("\n" + "="*80)
    
    return len(vectors_master), len(vectors_restaurant)

if __name__ == "__main__":
    try:
        master_count, restaurant_count = embed_schema_compliant_maass()
        print(f"\n✓ Successfully embedded {master_count + restaurant_count} total vectors!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
