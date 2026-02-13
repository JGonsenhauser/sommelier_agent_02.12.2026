#!/usr/bin/env python3
"""
Test the running API endpoint via HTTP to verify it works end-to-end.
Run this AFTER starting the API with start_api.bat
"""
import requests
import json

def test_api_endpoint():
    """Test the API endpoint via HTTP."""
    base_url = "http://localhost:8000"

    print("\n" + "="*60)
    print("Testing API Endpoint")
    print("="*60)

    # Test 1: Health check
    print("\n[1] Testing health check...")
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("[OK] API is running")
            print(f"    {response.json()}")
        else:
            print(f"[ERROR] Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("[ERROR] Cannot connect to API. Is it running on port 8000?")
        print("Run: start_api.bat")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

    # Test 2: Wine recommendation
    queries = [
        "light pinot noir",
        "pinot noir",
        "bold red wine under $100"
    ]

    for query in queries:
        print(f"\n[2] Testing query: '{query}'")
        try:
            response = requests.get(
                f"{base_url}/api/recommend",
                params={"query": query, "restaurant_id": "maass"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                wines = data.get("wines", [])
                print(f"[OK] Got {len(wines)} wines")

                for i, wine in enumerate(wines, 1):
                    print(f"\n  Wine {i}:")
                    print(f"    Text: {wine.get('text', 'N/A')}")
                    print(f"    Producer: {wine.get('producer')}")
                    print(f"    Price: ${wine.get('price')}")
                    print(f"    Region: {wine.get('region')}")
                    print(f"    Tasting Note: {wine.get('tasting_note', '')[:80]}...")

                    # Verify price is a string
                    price = wine.get('price')
                    if not isinstance(price, str):
                        print(f"    [WARNING] Price is {type(price).__name__}, expected str!")

                print(f"\n[SUCCESS] Query '{query}' completed successfully!")

            else:
                print(f"[ERROR] API returned status {response.status_code}")
                print(f"Response: {response.text}")
                return False

        except Exception as e:
            print(f"[ERROR] {type(e).__name__}: {e}")
            return False

    print("\n" + "="*60)
    print("[SUCCESS] All API tests passed!")
    print("="*60)
    return True

if __name__ == "__main__":
    import sys
    success = test_api_endpoint()
    sys.exit(0 if success else 1)
