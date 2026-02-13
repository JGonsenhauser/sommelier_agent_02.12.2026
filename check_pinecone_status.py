#!/usr/bin/env python3
"""Quick check of Pinecone index status and vector counts"""

from pinecone import Pinecone
from config import settings

# Initialize Pinecone
pc = Pinecone(api_key=settings.pinecone_api_key)
index = pc.Index(settings.pinecone_index_name)

print("=" * 80)
print("PINECONE INDEX STATUS CHECK")
print("=" * 80)

try:
    # Get index stats
    stats = index.describe_index_stats()
    print(f"\n✓ Connected to index: {settings.pinecone_index_name}")
    print(f"  Dimensions: {stats.get('dimension', 'N/A')}")
    print(f"  Total vector count: {stats.get('total_vector_count', 'N/A')}")
    
    # Check namespaces
    namespaces = stats.get('namespaces', {})
    print(f"\n📊 Namespace Details:")
    for ns_name, ns_stats in namespaces.items():
        vector_count = ns_stats.get('vector_count', 0)
        print(f"  • {ns_name}: {vector_count} vectors")
    
    # Verify key namespaces exist
    print(f"\n🔍 Key Namespace Checks:")
    if 'maass_wine_list' in namespaces:
        print(f"  ✅ 'maass_wine_list': {namespaces['maass_wine_list']['vector_count']} vectors")
    else:
        print(f"  ❌ 'maass_wine_list': NOT FOUND")
    
    if 'producers' in namespaces:
        print(f"  ✅ 'producers': {namespaces['producers']['vector_count']} vectors")
    else:
        print(f"  ❌ 'producers': NOT FOUND")
    
    if 'master' in namespaces:
        print(f"  ⚠️  'master': STILL EXISTS ({namespaces['master']['vector_count']} vectors) - should be deleted")
    else:
        print(f"  ✅ 'master': DELETED (as expected)")
    
except Exception as e:
    print(f"❌ Error checking Pinecone: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
