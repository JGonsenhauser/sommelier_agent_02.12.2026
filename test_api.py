"""
Test FastAPI mobile endpoint.
"""
import sys
from pathlib import Path
import time
import requests

sys.path.insert(0, str(Path(__file__).parent))

def test_api():
    API_URL = "http://127.0.0.1:8000"

    print('\n' + '='*60)
    print('Testing FastAPI Mobile Endpoint')
    print('='*60)

    # Test health check
    print('\n1. Testing health check...')
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            print(f'   [OK] API is online: {response.json()}')
        else:
            print(f'   [ERROR] Status code: {response.status_code}')
    except Exception as e:
        print(f'   [ERROR] Could not connect to API: {e}')
        print('\n   Please start the API server first:')
        print('   python -m uvicorn api.mobile_api:app --port 8000')
        return

    # Test recommendation endpoint
    print('\n2. Testing wine recommendation...')
    query = "Bold red wine for steak under 100"
    print(f'   Query: "{query}"')

    start = time.time()
    try:
        response = requests.post(
            f"{API_URL}/api/recommend",
            json={"query": query, "restaurant_id": "maass"},
            timeout=60
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            print(f'\n   [OK] Response time: {elapsed:.2f} seconds')
            print(f'   [OK] Wines returned: {len(data["wines"])}')
            print(f'   [OK] Processing time: {data["processing_time"]:.2f}s')

            print(f'\n   Recommendations:')
            for i, wine in enumerate(data["wines"], 1):
                title = f'{wine.get("vintage", "")} {wine["producer"]} {wine.get("wine_name", "")} {wine["region"]}'
                print(f'\n   {i}. {title.strip()}')
                print(f'      Price: ${wine.get("price", wine["price_range"])}')
                print(f'      Score: {wine["score"]:.3f}')
        else:
            print(f'   [ERROR] Status code: {response.status_code}')
            print(f'   Error: {response.text}')

    except Exception as e:
        print(f'   [ERROR] Request failed: {e}')

    # Test cached query
    print('\n3. Testing CACHED query (should be faster)...')
    start2 = time.time()
    try:
        response2 = requests.post(
            f"{API_URL}/api/recommend",
            json={"query": query, "restaurant_id": "maass"},
            timeout=60
        )
        elapsed2 = time.time() - start2

        if response2.status_code == 200:
            data2 = response2.json()
            print(f'\n   [OK] Cached response time: {elapsed2:.2f} seconds')
            print(f'   [OK] Processing time: {data2["processing_time"]:.2f}s')
            print(f'   [OK] Speed improvement: {elapsed/elapsed2:.1f}x faster')
        else:
            print(f'   [ERROR] Status code: {response2.status_code}')

    except Exception as e:
        print(f'   [ERROR] Request failed: {e}')

    print('\n' + '='*60)
    print('API Test Complete!')
    print('='*60)
    print('\nNext steps:')
    print('1. Open mobile interface: http://127.0.0.1:3000')
    print('2. Test on phone (see MOBILE_QUICKSTART.md)')
    print('3. Deploy to production (Railway + Vercel)')
    print('='*60 + '\n')

if __name__ == '__main__':
    test_api()
