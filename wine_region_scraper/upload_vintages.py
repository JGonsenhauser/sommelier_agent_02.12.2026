"""Load and upload wine vintage data to Pinecone."""
from src.vintage_builder import VintageBuilder
from src.pinecone_client import get_index

vb = VintageBuilder()
vb.load_from_excel('data/wine_vintages_notes.xlsx')

print(f'Loaded {len(vb.entries)} vintage entries')
stats = vb.get_stats()
print(f'Regions: {stats["regions"]}')
print(f'Vintage range: {stats["vintage_range"][0]} - {stats["vintage_range"][1]}')
print(f'Entries with ratings: {stats["entries_with_ratings"]} / {stats["count"]}')

# Show sample regions
print(f'\nSample regions:')
for region in sorted(stats["region_names"])[:10]:
    region_entries = [e for e in vb.entries if e.region == region]
    print(f'  {region}: {len(region_entries)} vintages')

# Sample entries
print(f'\nSample entries:')
for i, entry in enumerate(vb.entries[:5]):
    print(f'{i+1}. {entry.region} {entry.vintage} - Rating: {entry.rating}')
    print(f'   Notes: {entry.notes[:80]}...')

# Save as JSONL for inspection
vb.save_as_jsonl()

print(f'\nPushing to Pinecone namespace "vintages"...')
vb.push_to_pinecone(namespace='vintages')

index = get_index()
index_stats = index.describe_index_stats()
print(f'\nPinecone index stats:')
for namespace, stats in index_stats.get('namespaces', {}).items():
    print(f'  {namespace}: {stats["vector_count"]} vectors')
print(f'Total vectors in index: {index_stats["total_vector_count"]}')
