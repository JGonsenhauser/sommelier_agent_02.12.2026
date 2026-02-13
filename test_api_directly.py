#!/usr/bin/env python3
"""
Test the API endpoint directly to verify price types work correctly.
"""
from dotenv import load_dotenv
load_dotenv()

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from api.mobile_api import RecommendationRequest
from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender_optimized import OptimizedWineRecommender

def test_api_flow():
    """Simulate the API flow to test if price validation works."""
    print("\n" + "="*60)
    print("Testing API flow with actual recommender data")
    print("="*60)

    request = RecommendationRequest(
        query="pinot noir",
        restaurant_id="maass"
    )

    print(f"\n[1] Query: {request.query}")
    print(f"[2] Restaurant: {request.restaurant_id}")

    # Get recommender
    recommender = OptimizedWineRecommender(MAASS_CONFIG)

    # Get recommendations
    print("\n[3] Getting recommendations...")
    wines = recommender.get_full_recommendation(request.query)

    if not wines:
        print("[ERROR] No wines returned!")
        return

    print(f"[OK] Got {len(wines)} wines\n")

    # Try to create API response models
    from api.mobile_api import WineRecommendation

    print("[4] Converting to API response models...")
    try:
        for i, wine in enumerate(wines, 1):
            print(f"\nWine {i}:")
            print(f"  Producer: {wine['producer']}")

            # Show what we're passing
            price_val = wine.get("price", "")
            print(f"  Price from wine dict: {price_val} (type: {type(price_val).__name__})")

            # Defensively coerce
            price_str = str(price_val) if price_val else ""
            vintage_str = str(wine.get("vintage", "")) if wine.get("vintage") else ""

            print(f"  Price after coercion: {price_str} (type: {type(price_str).__name__})")

            # Try to create the model
            rec = WineRecommendation(
                wine_id=wine["wine_id"],
                producer=wine["producer"],
                wine_name=wine.get("wine_name", ""),
                region=wine["region"],
                country=wine.get("country", ""),
                vintage=vintage_str,
                price=price_str,
                text=wine.get("text", ""),
                grapes=wine.get("grapes", ""),
                wine_type=wine["wine_type"],
                price_range=wine["price_range"],
                tasting_note=wine.get("tasting_note", ""),
                food_pairing=wine.get("food_pairing"),
                score=float(wine["score"]),
            )

            print(f"  [OK] WineRecommendation model created successfully!")
            print(f"  Model price field: {rec.price} (type: {type(rec.price).__name__})")

    except Exception as e:
        print(f"\n[ERROR] Failed to create WineRecommendation model:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "="*60)
    print("[SUCCESS] All wines converted to API models successfully!")
    print("="*60)
    return True

if __name__ == "__main__":
    success = test_api_flow()
    sys.exit(0 if success else 1)
