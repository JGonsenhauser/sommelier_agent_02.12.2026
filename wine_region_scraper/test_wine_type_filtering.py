"""Verify wine_type filtering in Pinecone."""
from src.pinecone_client import get_index

index = get_index()

# Query for red wines only
print("RED WINES - Sample entries:\n")
red_results = index.query(
    namespace='wine_taxonomy',
    vector=[0.01]*1024,
    top_k=5,
    filter={"wine_type": {"$eq": "red"}},
    include_metadata=True
)

for match in red_results['matches']:
    meta = match['metadata']
    sub = f" ({meta.get('sub_region')})" if meta.get('sub_region') else ""
    print(f"{meta['country']}/{meta['region']}{sub}")
    print(f"  Type: {meta['wine_type']} | Grape: {meta['primary_grape']}")
    print(f"  Blends: {', '.join(meta.get('common_blends', []))}")
    print()

# Query for white wines only
print("\n" + "="*60)
print("WHITE WINES - Sample entries:\n")
white_results = index.query(
    namespace='wine_taxonomy',
    vector=[0.01]*1024,
    top_k=5,
    filter={"wine_type": {"$eq": "white"}},
    include_metadata=True
)

for match in white_results['matches']:
    meta = match['metadata']
    sub = f" ({meta.get('sub_region')})" if meta.get('sub_region') else ""
    print(f"{meta['country']}/{meta['region']}{sub}")
    print(f"  Type: {meta['wine_type']} | Grape: {meta['primary_grape']}")
    print()

# Query for Burgundy specifically
print("\n" + "="*60)
print("BURGUNDY - All entries (red and white separated):\n")
burgundy_results = index.query(
    namespace='wine_taxonomy',
    vector=[0.01]*1024,
    top_k=10,
    filter={"region": {"$eq": "Burgundy"}},
    include_metadata=True
)

for match in burgundy_results['matches']:
    meta = match['metadata']
    sub = f" > {meta.get('sub_region')}" if meta.get('sub_region') else ""
    print(f"{meta['wine_type'].upper()}: {meta['region']}{sub} - {meta['primary_grape']}")
