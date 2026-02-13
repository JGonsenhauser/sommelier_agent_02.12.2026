#!/usr/bin/env python3
"""Check what wines are actually in maass_wine_list namespace."""
from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
import os

# Connect using XAI embedding dimensions
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    host=os.getenv("PINECONE_HOST")
)

print("\n" + "="*60)
print("Checking wines in maass_wine_list namespace")
print("="*60)

# Get XAI embedding for a simple query
from openai import OpenAI
xai_client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

# Test 1: Search for "pinot noir"
print("\n[1] Searching for 'pinot noir' in maass_wine_list...")
try:
    response = xai_client.embeddings.create(
        model="grok-embedding",
        input="pinot noir"
    )
    query_vector = response.data[0].embedding

    results = index.query(
        namespace="maass_wine_list",
        vector=query_vector,
        top_k=5,
        include_metadata=True
    )

    print(f"Found {len(results['matches'])} wines\n")
    for i, match in enumerate(results['matches'], 1):
        m = match.get('metadata', {})
        print(f"{i}. {m.get('producer', 'N/A')} - {m.get('wine_name', '')}")
        print(f"   Region: {m.get('region', 'N/A')}, Grapes: {m.get('grapes', 'N/A')}")
        print(f"   Price: ${m.get('price', 'N/A')}, Range: {m.get('price_range', 'N/A')}")
        print(f"   Score: {match['score']:.4f}\n")

except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Search for "cabernet sauvignon napa valley"
print("\n[2] Searching for 'cabernet sauvignon napa valley' in maass_wine_list...")
try:
    response = xai_client.embeddings.create(
        model="grok-embedding",
        input="cabernet sauvignon napa valley"
    )
    query_vector = response.data[0].embedding

    results = index.query(
        namespace="maass_wine_list",
        vector=query_vector,
        top_k=10,
        include_metadata=True
    )

    print(f"Found {len(results['matches'])} wines\n")

    # Check if ANY are from Napa
    napa_wines = [m for m in results['matches'] if 'napa' in m.get('metadata', {}).get('region', '').lower()]
    print(f"Wines from Napa Valley: {len(napa_wines)}")

    for i, match in enumerate(results['matches'][:10], 1):
        m = match.get('metadata', {})
        print(f"{i}. {m.get('producer', 'N/A')}")
        print(f"   Region: {m.get('region', 'N/A')}, Grapes: {m.get('grapes', 'N/A')}")
        print(f"   Price: ${m.get('price', 'N/A')}")
        print(f"   Score: {match['score']:.4f}\n")

except Exception as e:
    print(f"ERROR: {e}")

# Test 3: Check if there ARE any Napa wines at all
print("\n[3] Checking if maass_wine_list has ANY Napa Valley wines...")
try:
    # Try to filter by region metadata
    results = index.query(
        namespace="maass_wine_list",
        vector=[0.01] * 1024,  # Dummy vector
        top_k=100,
        include_metadata=True,
        filter={"region": {"$eq": "Napa Valley"}}
    )

    print(f"Wines with region='Napa Valley': {len(results['matches'])}")

    if results['matches']:
        for i, match in enumerate(results['matches'][:5], 1):
            m = match.get('metadata', {})
            print(f"{i}. {m.get('producer')} - {m.get('grapes', 'N/A')}")
            print(f"   Price: ${m.get('price', 'N/A')}\n")

except Exception as e:
    print(f"ERROR: {e}")
