"""Debug script to inspect Pinecone upload data."""
from src.taxonomy_builder import TaxonomyBuilder
import json

tb = TaxonomyBuilder()
tb.load_from_csv('data/wine_taxonomy.csv')

# Inspect first entry
entry = tb.entries[0]
print("First entry to_dict():")
print(json.dumps(entry.to_dict(), indent=2))

# Inspect cleaned metadata
metadata = {k: v for k, v in entry.to_dict().items() if v is not None}
metadata['region_key'] = f"{entry.country}/{entry.region}"
print("\nCleaned metadata:")
print(json.dumps(metadata, indent=2))

# Check for any remaining None values
for k, v in metadata.items():
    if v is None:
        print(f"WARNING: Field '{k}' is still None!")
    elif isinstance(v, list) and None in v:
        print(f"WARNING: Field '{k}' contains None in list!")
