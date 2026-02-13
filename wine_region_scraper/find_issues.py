"""Find entries with issues."""
from src.taxonomy_builder import TaxonomyBuilder

tb = TaxonomyBuilder()
tb.load_from_csv('data/wine_taxonomy.csv')

for i, e in enumerate(tb.entries):
    if not e.common_blends or None in e.common_blends:
        print(f"{i}: {e.region} - blends={e.common_blends}")
