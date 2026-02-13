#!/usr/bin/env python3
"""Test Pinecone directly to see what's actually there."""
from dotenv import load_dotenv
load_dotenv()

from pinecone import Pinecone
import os

# Connect to Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(
    name=os.getenv("PINECONE_INDEX_NAME"),
    host=os.getenv("PINECONE_HOST")
)

print("\n" + "="*60)
print("Testing Pinecone Direct Access")
print("="*60)

# Test 1: Check if namespace exists
print("\n[1] Checking namespace 'maass_wine_list'...")
try:
    # Query with no vector (just to test namespace)
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")

    if 'namespaces' in stats and 'maass_wine_list' in stats['namespaces']:
        count = stats['namespaces']['maass_wine_list'].get('vector_count', 0)
        print(f"[OK] Namespace 'maass_wine_list' exists with {count} vectors")
    else:
        print(f"[ERROR] Namespace 'maass_wine_list' NOT FOUND!")
        print(f"Available namespaces: {list(stats.get('namespaces', {}).keys())}")

except Exception as e:
    print(f"[ERROR] {e}")

# Test 2: Fetch a sample vector to see metadata structure
print("\n[2] Fetching sample vectors from 'maass_wine_list'...")
try:
    # List some IDs from the namespace
    response = index.query(
        namespace="maass_wine_list",
        vector=[0.1] * 1536,  # OpenAI embedding dimension
        top_k=3,
        include_metadata=True
    )

    if response['matches']:
        print(f"[OK] Found {len(response['matches'])} sample wines\n")

        for i, match in enumerate(response['matches'], 1):
            metadata = match.get('metadata', {})
            print(f"Wine {i}:")
            print(f"  ID: {match['id']}")
            print(f"  Producer: {metadata.get('producer', 'N/A')}")
            print(f"  Region: {metadata.get('region', 'N/A')}")
            print(f"  Grapes: {metadata.get('grapes', 'N/A')}")
            print(f"  Price: {metadata.get('price', 'N/A')} (type: {type(metadata.get('price')).__name__})")
            print(f"  Price Range: {metadata.get('price_range', 'N/A')}")
            print(f"  Wine Type: {metadata.get('wine_type', 'N/A')}")
            print(f"  Text: {metadata.get('text', 'N/A')[:80]}...")
            print()
    else:
        print("[ERROR] No vectors found in namespace!")

except Exception as e:
    print(f"[ERROR] {e}")

# Test 3: Try a search with NO filters
print("\n[3] Testing search for 'pinot noir' with NO price filter...")
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Get embedding for "pinot noir"
    embedding_response = client.embeddings.create(
        model="text-embedding-3-small",
        input="pinot noir"
    )
    query_vector = embedding_response.data[0].embedding

    # Search WITHOUT filters
    response = index.query(
        namespace="maass_wine_list",
        vector=query_vector,
        top_k=5,
        include_metadata=True
    )

    print(f"[OK] Found {len(response['matches'])} wines for 'pinot noir'\n")
    for i, match in enumerate(response['matches'], 1):
        metadata = match.get('metadata', {})
        print(f"{i}. {metadata.get('producer')} - {metadata.get('region')}")
        print(f"   Price: ${metadata.get('price', 'N/A')}, Range: {metadata.get('price_range', 'N/A')}")
        print(f"   Score: {match['score']:.4f}")

except Exception as e:
    print(f"[ERROR] {e}")

# Test 4: Try search WITH price filter
print("\n[4] Testing search for 'pinot noir' WITH price filter...")
try:
    # Search WITH price_range filter
    response = index.query(
        namespace="maass_wine_list",
        vector=query_vector,
        top_k=5,
        include_metadata=True,
        filter={"price_range": {"$in": ["$50-100", "$100-200"]}}
    )

    print(f"[OK] Found {len(response['matches'])} wines with price filter\n")
    if response['matches']:
        for i, match in enumerate(response['matches'], 1):
            metadata = match.get('metadata', {})
            print(f"{i}. {metadata.get('producer')} - {metadata.get('region')}")
            print(f"   Price: ${metadata.get('price', 'N/A')}, Range: {metadata.get('price_range', 'N/A')}")
    else:
        print("NO RESULTS WITH FILTER - This is the problem!")

except Exception as e:
    print(f"[ERROR] {e}")
