#!/usr/bin/env python
"""Run MAASS wine list ingest to Pinecone."""
from pathlib import Path
from data.maass_ingest import ingest_maass_list

source = Path('MAASS_Wine_List.xlsx')
if not source.exists():
    raise FileNotFoundError(f'{source} not found')

print(f'Using source: {source}')
embedded = ingest_maass_list(source)
print(f'\n✓ SUCCESS: Embedded {embedded} wines into Pinecone')
print(f'  - Index: wineregionscrape')
print(f'  - Namespace: maass_wine_list')
print(f'  - Producer namespace: producers')
