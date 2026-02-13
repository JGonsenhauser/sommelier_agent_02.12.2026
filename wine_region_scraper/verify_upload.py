"""Query Pinecone to verify uploaded data."""
from src.pinecone_client import get_index
import json

index = get_index()
result = index.query(
    namespace='wine_taxonomy',
    vector=[0.01]*1024,
    top_k=3,
    include_metadata=True
)

print("Sample entries from Pinecone:\n")
for match in result['matches']:
    print(f"{match['id']}: Score={match['score']:.4f}")
    metadata = match.get('metadata', {})
    print(f"  Region: {metadata.get('country')}/{metadata.get('region')}")
    print(f"  Grape: {metadata.get('primary_grape')}")
    print(f"  Blends: {metadata.get('common_blends', [])}")
    print()
