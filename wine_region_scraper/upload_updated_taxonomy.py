"""Load and upload updated wine taxonomy with wine_type field."""
from src.taxonomy_builder import TaxonomyBuilder
from src.pinecone_client import get_index

tb = TaxonomyBuilder()
tb.load_from_csv('data/wine_taxonomy.csv')

print(f'Loaded {len(tb.entries)} entries')
stats = tb.get_stats()
print(f'Countries: {stats["countries"]}')
print(f'Regions: {stats["regions"]}')

# Count wine types
wine_types = {}
for e in tb.entries:
    wine_types[e.wine_type] = wine_types.get(e.wine_type, 0) + 1

print(f'\nWine type breakdown:')
for wtype, count in sorted(wine_types.items()):
    print(f'  {wtype}: {count}')

# Sample entries
print(f'\nSample entries:')
for i, entry in enumerate(tb.entries[:3]):
    print(f'{i+1}. {entry.region} ({entry.wine_type}) - {entry.primary_grape}')
    if entry.sub_region:
        print(f'   Sub-region: {entry.sub_region}')

print(f'\nPushing to Pinecone...')
tb.push_to_pinecone(namespace='wine_taxonomy')

index = get_index()
index_stats = index.describe_index_stats()
print(f'\nTotal vectors in Pinecone: {index_stats["total_vector_count"]}')
