#!/usr/bin/env python3
"""Test tasting note generation directly."""
from dotenv import load_dotenv
load_dotenv()

from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender_optimized import OptimizedWineRecommender

def test_specific_wines():
    """Test tasting note generation for specific wines that are failing."""
    print("\n" + "="*60)
    print("Testing tasting note generation for specific wines")
    print("="*60)

    recommender = OptimizedWineRecommender(MAASS_CONFIG)

    wines = [
        {
            "producer": "Mongeard-Mugneret",
            "region": "Hautes Côtes de Nuits",
            "wine_name": "",
            "grapes": "Pinot Noir",
            "wine_type": "red"
        },
        {
            "producer": "DuMOL",
            "region": "Sonoma Coast",
            "wine_name": "MacIntyre Estate Vineyard",
            "grapes": "Pinot Noir",
            "wine_type": "red"
        }
    ]

    for i, wine in enumerate(wines, 1):
        print(f"\n{'-'*60}")
        print(f"Wine {i}: {wine['producer']} - {wine['region']}")
        print(f"{'-'*60}")

        note = recommender.get_tasting_note_cached(
            wine['producer'],
            wine['region'],
            wine['wine_name'],
            wine['grapes'],
            wine['wine_type']
        )

        print(f"\nGenerated tasting note:")
        print(f"{note}\n")
        print(f"Length: {len(note)} characters")
        print(f"Valid: {len(note) > 50 and 'No tasting note' not in note}")

if __name__ == "__main__":
    test_specific_wines()
