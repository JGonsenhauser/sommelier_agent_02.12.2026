#!/usr/bin/env python3
"""Test the exact queries the user tried."""
import requests

base_url = "http://localhost:8000"

queries = [
    "Light pinot noir around 90",
    "cabernet sauvignon from napa valley",
    "how about a cabernet sauvignon from napa vallet"  # With typo as user typed
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: '{query}'")
    print('='*60)

    try:
        response = requests.get(
            f"{base_url}/api/recommend",
            params={"query": query, "restaurant_id": "maass"},
            timeout=60
        )

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            wines = data.get("wines", [])
            print(f"Wines found: {len(wines)}")

            if wines:
                for i, wine in enumerate(wines, 1):
                    print(f"\n{i}. {wine.get('producer')} - {wine.get('region')}")
                    print(f"   Price: ${wine.get('price')}")
            else:
                print("NO WINES RETURNED")
                print(f"Full response: {data}")
        else:
            print(f"ERROR: {response.text}")

    except Exception as e:
        print(f"EXCEPTION: {e}")
