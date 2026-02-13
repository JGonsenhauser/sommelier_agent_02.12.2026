"""
Clean Pinecone index and re-embed with new schema:
1. Delete 'master' namespace completely
2. Delete 'maass_wine_list' namespace completely  
3. Re-embed MAASS to 'maass_wine_list' only
4. Embed producers to 'producers' namespace
"""
import pandas as pd
import hashlib
from pathlib import Path
from data.embedding_pipeline import EmbeddingPipeline
from config import settings

def generate_master_vector_id(producer, label, grapes, region, country):
    """Generate deterministic master vector ID."""
    text = f"{producer}_{label or ''}_{grapes}_{region}_{country}"
    return hashlib.md5(text.encode()).hexdigest()

def delete_namespaces():
    """Delete master and maass_wine_list namespaces."""
    print("\n" + "="*80)
    print("STEP 1: DELETE EXISTING NAMESPACES")
    print("="*80)
    
    pipeline = EmbeddingPipeline()
    
    print("\n🗑️  Deleting 'master' namespace...")
    try:
        pipeline.index.delete(delete_all=True, namespace='master')
        print("  ✓ 'master' namespace deleted")
    except Exception as e:
        print(f"  Note: {e}")
    
    print("\n🗑️  Deleting 'maass_wine_list' namespace...")
    try:
        pipeline.index.delete(delete_all=True, namespace='maass_wine_list')
        print("  ✓ 'maass_wine_list' namespace deleted")
    except Exception as e:
        print(f"  Note: {e}")
    
    print("\n✅ Namespace cleanup complete!")
    return pipeline

def embed_maass_to_restaurant_namespace(pipeline):
    """Embed schema-compliant MAASS to maass_wine_list namespace only."""
    print("\n" + "="*80)
    print("STEP 2: EMBED MAASS WINES TO 'maass_wine_list' NAMESPACE")
    print("="*80)
    
    csv_path = Path('data/raw/maass_wine_list_schema_compliant.csv')
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} not found")
    
    df = pd.read_csv(csv_path)
    print(f"\n✓ Loaded {len(df)} wines from {csv_path}")
    
    batch_size = 100
    vectors = []
    
    print(f"\n📝 Preparing {len(df)} wines for embedding...")
    
    for idx, row in df.iterrows():
        # Generate master vector ID for deterministic reference
        master_id = generate_master_vector_id(
            row['producer'],
            row.get('label', ''),
            row['grapes'],
            row['region'],
            row['country']
        )
        
        # Get embedding
        embedding = pipeline.get_embeddings([row['text']])[0]
        
        # Create vector with FULL schema (master + restaurant fields)
        vector_id = f"maass_{row['list_id']}_wine_{master_id[:8]}"
        vector = {
            "id": vector_id,
            "values": embedding,
            "metadata": {
                # Core Metadata
                "producer": row['producer'],
                "label": row.get('label', ''),
                "grapes": row['grapes'],
                "region": row['region'],
                "major_region": row.get('major_region', row['region']),
                "country": row['country'],
                "text": row['text'],
                "sync_version": 1,
                # Restaurant-Specific
                "price_range": row['price_range'],
                "price": row.get('price'),
                "tasting_keywords": row['tasting_keywords'],
                "list_id": row['list_id'],
                "qr_id": row['qr_id'],
                "restaurant": row['restaurant'],
                "source": "maass_schema_v2"
            }
        }
        vectors.append(vector)
        
        if (idx + 1) % 50 == 0 or (idx + 1) == len(df):
            print(f"  Prepared {idx + 1}/{len(df)} wines")
    
    # Upsert to Pinecone
    print(f"\n🔼 Upserting {len(vectors)} wines to 'maass_wine_list' namespace...")
    
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i+batch_size]
        pipeline.index.upsert(vectors=batch, namespace='maass_wine_list')
        print(f"  ✓ Batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")
    
    print(f"\n✅ MAASS embedding complete! {len(vectors)} vectors in 'maass_wine_list'")
    return len(vectors)

def embed_producers_to_producers_namespace(pipeline):
    """Embed producers to 'producers' namespace."""
    print("\n" + "="*80)
    print("STEP 3: EMBED PRODUCERS TO 'producers' NAMESPACE")
    print("="*80)
    
    xlsx_path = Path('wine_producer_scaper/producer_list_schema_compliant.xlsx')
    if not xlsx_path.exists():
        raise FileNotFoundError(f"{xlsx_path} not found")
    
    df = pd.read_excel(xlsx_path)
    print(f"\n✓ Loaded {len(df)} producers from {xlsx_path}")
    
    batch_size = 100
    vectors = []
    
    print(f"\n📝 Preparing {len(df)} producers for embedding...")
    
    for idx, row in df.iterrows():
        # Generate deterministic producer ID
        producer_id = generate_master_vector_id(
            row['producer'],
            row.get('label', ''),
            row['grapes'],
            row['region'],
            row['country']
        )
        
        # Get embedding
        embedding = pipeline.get_embeddings([row['text']])[0]
        
        # Create vector (core metadata only, no restaurant fields)
        vector = {
            "id": producer_id,
            "values": embedding,
            "metadata": {
                # Core Metadata
                "producer": row['producer'],
                "label": row.get('label', ''),
                "grapes": row['grapes'],
                "region": row['region'],
                "major_region": row.get('major_region', row['region']),
                "country": row['country'],
                "text": row['text'],
                "sync_version": 1,
                "source": "producers_schema_v2"
            }
        }
        vectors.append(vector)
        
        if (idx + 1) % 100 == 0 or (idx + 1) == len(df):
            print(f"  Prepared {idx + 1}/{len(df)} producers")
    
    # Upsert to Pinecone
    print(f"\n🔼 Upserting {len(vectors)} producers to 'producers' namespace...")
    
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i+batch_size]
        pipeline.index.upsert(vectors=batch, namespace='producers')
        print(f"  ✓ Batch {i//batch_size + 1}/{(len(vectors)-1)//batch_size + 1}")
    
    print(f"\n✅ PRODUCERS embedding complete! {len(vectors)} vectors in 'producers'")
    return len(vectors)

if __name__ == "__main__":
    try:
        print("\n" + "="*80)
        print("PINECONE INDEX REBUILD - SCHEMA V2")
        print("="*80)
        print("Index: wineregionscrape")
        print("="*80)
        
        # Step 1: Delete namespaces
        pipeline = delete_namespaces()
        
        # Step 2: Embed MAASS
        maass_count = embed_maass_to_restaurant_namespace(pipeline)
        
        # Step 3: Embed Producers
        producer_count = embed_producers_to_producers_namespace(pipeline)
        
        # Summary
        print("\n" + "="*80)
        print("✅ REBUILD COMPLETE!")
        print("="*80)
        print(f"\nIndex: wineregionscrape")
        print(f"  • 'maass_wine_list' namespace: {maass_count} vectors")
        print(f"  • 'producers' namespace: {producer_count} vectors")
        print(f"  • 'master' namespace: DELETED")
        print(f"\nTotal vectors: {maass_count + producer_count}")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
