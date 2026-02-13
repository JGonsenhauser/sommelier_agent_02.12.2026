#!/usr/bin/env python3
"""
Test what type the price field actually is when returned from recommender.
"""
from dotenv import load_dotenv
load_dotenv()

import sys
from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender_optimized import OptimizedWineRecommender

def test_price_types():
    """Check the actual type of price fields returned."""
    print("\n" + "="*60)
    print("Testing actual price field types from recommender")
    print("="*60)

    print("\n[1] Creating recommender...")
    recommender = OptimizedWineRecommender(MAASS_CONFIG)
    print("[OK] Recommender created")

    print("\n[2] Getting recommendations for 'pinot noir'...")
    wines = recommender.get_full_recommendation("pinot noir")

    if not wines:
        print("[ERROR] No wines returned!")
        return

    print(f"[OK] Got {len(wines)} wines\n")

    for i, wine in enumerate(wines, 1):
        print(f"Wine {i}:")
        print(f"  Producer: {wine['producer']}")
        print(f"  Wine Name: {wine.get('wine_name', 'N/A')}")

        # Check price type
        price = wine.get('price')
        print(f"  Price value: {price}")
        print(f"  Price type: {type(price)}")
        print(f"  Price is string: {isinstance(price, str)}")
        print(f"  Price is int: {isinstance(price, int)}")
        print(f"  Price is float: {isinstance(price, float)}")

        # Check what's in metadata
        if 'metadata' in wine:
            meta_price = wine['metadata'].get('price')
            print(f"  Metadata price value: {meta_price}")
            print(f"  Metadata price type: {type(meta_price)}")

        print()

if __name__ == "__main__":
    test_price_types()
