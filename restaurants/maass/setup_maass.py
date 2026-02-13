"""
Complete setup script for MAASS restaurant.
Ingests wine list, generates QR code, and validates everything.
"""
import sys
import logging
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from data.maass_ingest import ingest_maass_list
from restaurants.qr_generator import RestaurantQRGenerator
from restaurants.restaurant_config import MAASS_CONFIG
from restaurants.wine_recommender import WineRecommender

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_maass_complete():
    """Complete MAASS setup: ingest wines + generate QR code + test."""

    print("\n" + "="*60)
    print("MAASS Restaurant Sommelier Setup")
    print("="*60 + "\n")

    # Step 1: Find wine list file
    print("Step 1: Locating wine list...")
    root_dir = Path(__file__).parent.parent.parent
    xlsx_file = root_dir / "MAASS_Wine_List.xlsx"
    pdf_file = root_dir / "MAASS Beverage List 1.17.26.docx editing .docx.pdf"

    if xlsx_file.exists():
        source = xlsx_file
        print(f"[OK] Found: {xlsx_file.name}")
    elif pdf_file.exists():
        source = pdf_file
        print(f"[OK] Found: {pdf_file.name}")
    else:
        print("[ERROR] No wine list file found!")
        print(f"  Expected: {xlsx_file} or {pdf_file}")
        return False

    # Step 2: Ingest wine list
    print(f"\nStep 2: Ingesting {source.name}...")
    print("(This may take a few minutes to process and embed all wines)")

    try:
        embedded_count = ingest_maass_list(
            source_path=source,
            business_id=MAASS_CONFIG.restaurant_id,
            business_name=MAASS_CONFIG.name,
            location=MAASS_CONFIG.location,
            list_id=MAASS_CONFIG.namespace,
            namespace=MAASS_CONFIG.namespace,
            producers_namespace=MAASS_CONFIG.producers_namespace
        )

        print(f"[OK] Successfully embedded {embedded_count} wines")
        print(f"  - Namespace: {MAASS_CONFIG.namespace}")
        print(f"  - QR ID: {MAASS_CONFIG.qr_id}")

        # Update wine count
        MAASS_CONFIG.wine_count = embedded_count

    except Exception as e:
        print(f"[ERROR] Error ingesting wine list: {e}")
        logger.exception("Ingestion failed")
        return False

    # Step 3: Generate QR code
    print("\nStep 3: Generating QR code...")

    try:
        generator = RestaurantQRGenerator(base_url="http://localhost:8501")
        qr_path = generator.generate_qr_code(MAASS_CONFIG)

        print(f"[OK] QR code generated: {qr_path}")
        print(f"  - Scan URL: http://localhost:8501/?restaurant={MAASS_CONFIG.restaurant_id}")
        print(f"  - For production, regenerate with your deployment URL")

    except Exception as e:
        print(f"[ERROR] Error generating QR code: {e}")
        logger.exception("QR generation failed")
        return False

    # Step 4: Test recommendations
    print("\nStep 4: Testing wine recommendations...")

    try:
        recommender = WineRecommender(MAASS_CONFIG)

        test_query = "I want a bold red wine for steak dinner"
        print(f"\n  Test query: '{test_query}'")

        wines = recommender.get_full_recommendation(test_query)

        if wines:
            print(f"\n  [OK] Found {len(wines)} recommendations")

            for i, wine in enumerate(wines, 1):
                print(f"  {i}. {wine['producer']} ({wine['region']})")
                print(f"     Type: {wine['wine_type']} | Price: ${wine.get('price', wine.get('price_range'))}")
        else:
            print("  [WARN] No wines returned for test query")

    except Exception as e:
        print(f"  [ERROR] Error testing recommendations: {e}")
        logger.exception("Recommendation test failed")
        return False

    # Success summary
    print("\n" + "="*60)
    print("[SUCCESS] MAASS Setup Complete!")
    print("="*60)
    print(f"\nRestaurant: {MAASS_CONFIG.name}")
    print(f"Wines loaded: {embedded_count}")
    print(f"QR Code: {qr_path}")
    print(f"\nNext steps:")
    print(f"1. Run the Streamlit app:")
    print(f"   streamlit run restaurants/app.py")
    print(f"\n2. Or run MAASS-specific app:")
    print(f"   streamlit run restaurants/maass/maass_app.py")
    print(f"\n3. Scan the QR code at {qr_path} to test")
    print(f"\n4. For production deployment:")
    print(f"   - Update base_url in qr_generator.py")
    print(f"   - Regenerate QR code")
    print(f"   - Deploy Streamlit app")
    print("="*60 + "\n")

    return True


if __name__ == "__main__":
    success = setup_maass_complete()
    sys.exit(0 if success else 1)
