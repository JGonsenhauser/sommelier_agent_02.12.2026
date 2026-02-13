"""
Test optimized recommender performance.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender_optimized import OptimizedWineRecommender

def test_performance():
    print('\n' + '='*60)
    print('Testing Optimized Recommender Performance')
    print('='*60)

    recommender = OptimizedWineRecommender(MAASS_CONFIG)

    # Test query
    query = 'Bold red wine for steak under 100'
    print(f'\nQuery: "{query}"')
    print('-' * 60)

    start = time.time()
    wines = recommender.get_full_recommendation(query)
    elapsed = time.time() - start

    print(f'\n[OK] Response time: {elapsed:.2f} seconds')
    print(f'[OK] Wines returned: {len(wines)}')

    if wines:
        print(f'\nRecommendations:')
        for i, wine in enumerate(wines, 1):
            print(f'\n{i}. {wine.get("vintage", "")} {wine["producer"]} {wine.get("wine_name", "")} {wine["region"]}')
            print(f'   Price: ${wine.get("price", wine["price_range"])}')
            print(f'   Score: {wine["score"]:.3f}')

    print('\n' + '='*60)
    print('Testing CACHED query (should be much faster)')
    print('='*60)

    # Test same query again to see caching effect
    start2 = time.time()
    wines2 = recommender.get_full_recommendation(query)
    elapsed2 = time.time() - start2

    print(f'\n[OK] Cached response time: {elapsed2:.2f} seconds')
    print(f'[OK] Speed improvement: {elapsed/elapsed2:.1f}x faster')

    print('\n' + '='*60)
    print('PERFORMANCE SUMMARY')
    print('='*60)
    print(f'First query:  {elapsed:.2f}s')
    print(f'Cached query: {elapsed2:.2f}s')
    print(f'Improvement:  {elapsed/elapsed2:.1f}x faster with caching')
    print(f'\nAPI Calls Estimate:')
    print(f'  - First query:  ~8-10 API calls (search + selection + 2 enrichments)')
    print(f'  - Cached query: ~3-4 API calls (search + selection, notes/pairings cached)')
    print('='*60 + '\n')

if __name__ == '__main__':
    test_performance()
