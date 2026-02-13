#!/usr/bin/env python3
"""
Debug script to find why 'light pinot noir' query fails.
"""
from dotenv import load_dotenv
load_dotenv()

import sys
import logging
from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender_optimized import OptimizedWineRecommender

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_recommendation(query: str):
    """Test recommendation step by step with detailed error reporting."""
    print("\n" + "="*60)
    print(f"Debugging: '{query}'")
    print("="*60)

    try:
        print("\n[Step 1] Initializing recommender...")
        recommender = OptimizedWineRecommender(MAASS_CONFIG)
        print("[OK] Recommender initialized")

        print("\n[Step 2] Searching for wines...")
        matches = recommender.pipeline.search_similar_wines(
            query_text=query,
            qr_id=MAASS_CONFIG.qr_id,
            list_id=MAASS_CONFIG.namespace,
            top_k=10,
            namespace=MAASS_CONFIG.namespace
        )
        print(f"[OK] Found {len(matches)} matching wines")

        if not matches:
            print("[ERROR] No wines found - query failed at search stage")
            return False

        print("\n[Step 3] Enriching wine metadata...")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            enriched = list(executor.map(recommender.enrich_wine_metadata, matches))
        print(f"[OK] Enriched {len(enriched)} wines")

        # Show first wine
        if enriched:
            wine = enriched[0]
            print(f"\n  Sample wine:")
            print(f"  - Producer: {wine['producer']}")
            print(f"  - Wine name: {wine.get('wine_name', 'N/A')}")
            print(f"  - Region: {wine['region']}")
            print(f"  - Grapes: {wine.get('grapes', 'N/A')}")
            print(f"  - Text field: {wine.get('text', 'N/A')}")

        print("\n[Step 4] Selecting best 2 wines with LLM...")
        try:
            selected = recommender.select_best_two_wines(query, enriched)
            print(f"[OK] Selected {len(selected)} wines")

            for i, wine in enumerate(selected, 1):
                print(f"\n  Wine {i}:")
                print(f"  - Producer: {wine['producer']}")
                print(f"  - Wine name: {wine.get('wine_name', 'N/A')}")
                print(f"  - Region: {wine['region']}")

        except Exception as e:
            print(f"[ERROR] ERROR in wine selection:")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n[Step 5] Generating tasting notes...")
        try:
            for wine in selected:
                print(f"\n  Processing: {wine['producer']}...")

                # Check existing tasting note
                existing_note = wine['metadata'].get('tasting_note', '')
                print(f"    Existing note: {existing_note[:50] if existing_note else 'None'}...")

                # Get or generate tasting note
                tasting_note = wine['metadata'].get('tasting_note', '')
                if not tasting_note or len(tasting_note) < 20:
                    print(f"    Generating new tasting note...")
                    tasting_note = recommender.get_tasting_note_cached(
                        wine['producer'],
                        wine['region'],
                        wine['wine_name'],
                        wine['grapes'],
                        wine['wine_type']
                    )

                # Ensure fallback
                if not tasting_note or len(tasting_note) < 10:
                    tasting_note = f"A {wine['wine_type']} from {wine['region']} featuring {wine.get('grapes', 'classic varietals')}."

                print(f"    [OK] Final note: {tasting_note[:50]}...")
                wine['tasting_note'] = tasting_note
                wine['food_pairing'] = None

        except Exception as e:
            print(f"\n[ERROR] ERROR in tasting note generation:")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

        print("\n" + "="*60)
        print("[OK] ALL STEPS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print(f"\nFinal wines: {len(selected)}")
        for i, wine in enumerate(selected, 1):
            print(f"\n{i}. {wine.get('text', '')} {wine['producer']} {wine.get('wine_name', '')}")
            print(f"   Price: ${wine.get('price', 'N/A')}")
            print(f"   Tasting Note: {wine['tasting_note'][:100]}...")

        return True

    except Exception as e:
        print(f"\n[ERROR] FATAL ERROR:")
        print(f"  {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    queries = [
        "light pinot noir",
        "pinot noir",
        "bold red wine under $100"
    ]

    for query in queries:
        success = debug_recommendation(query)
        if not success:
            print(f"\n[WARNING]  Query '{query}' FAILED")
            print("Fix this issue before trying the next query\n")
            break
        print("\n" + "="*60 + "\n")
