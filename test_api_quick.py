#!/usr/bin/env python3
"""Quick API test with one query."""
import requests

base_url = "http://localhost:8000"

print("\nTesting: pinot noir\n")
try:
    response = requests.get(
        f"{base_url}/api/recommend",
        params={"query": "pinot noir", "restaurant_id": "maass"},
        timeout=60  # Longer timeout for first query
    )

    if response.status_code == 200:
        data = response.json()
        wines = data.get("wines", [])
        print(f"[OK] Got {len(wines)} wines in {data['processing_time']:.2f}s\n")

        for i, wine in enumerate(wines, 1):
            print(f"{i}. {wine.get('text', 'N/A')}")
            print(f"   Producer: {wine.get('producer')}")
            print(f"   Price: ${wine.get('price')}")
            print(f"   Tasting Note: {wine.get('tasting_note', '')[:100]}...")
            print()
    else:
        print(f"ERROR: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"ERROR: {e}")
