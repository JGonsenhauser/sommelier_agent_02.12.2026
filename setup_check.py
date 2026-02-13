"""
Quick setup and testing utilities for Wine Sommelier Agent.
"""
import sys
from pathlib import Path


def check_environment():
    """Check if environment is properly configured."""
    print("Checking Wine Sommelier Agent setup...\n")
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found!")
        print("   Create .env file from .env.example and add your API keys")
        return False
    else:
        print("✓ .env file exists")
    
    # Check required packages
    required_packages = [
        "openai",
        "cryptography",
        "redis",
        "pinecone",
        "pandas",
        "streamlit",
        "fastapi"
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} installed")
        except ImportError:
            missing.append(package)
            print(f"❌ {package} not installed")
    
    if missing:
        print(f"\nInstall missing packages: pip install {' '.join(missing)}")
        return False
    
    print("\n✓ All dependencies installed!")
    
    # Check Redis connection
    try:
        import redis
        from config import settings
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True
        )
        r.ping()
        print("✓ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("   Make sure Redis is running (see README for instructions)")
    
    return True


def create_sample_wine_list():
    """Create a sample wine list Excel file for testing."""
    import pandas as pd
    
    sample_wines = [
        {
            "producer": "Caymus Vineyards",
            "wine_name": "Special Selection Cabernet Sauvignon",
            "region": "Napa Valley",
            "country": "USA",
            "vintage": 2019,
            "price": 145.00,
            "grapes": "Cabernet Sauvignon",
            "wine_type": "red",
            "tasting_note": "Rich and full-bodied with notes of dark cherry, cassis, and vanilla. Silky tannins with a long, elegant finish.",
            "alcohol_content": 14.5
        },
        {
            "producer": "Domaine Leflaive",
            "wine_name": "Puligny-Montrachet",
            "region": "Burgundy",
            "country": "France",
            "vintage": 2020,
            "price": 165.00,
            "grapes": "Chardonnay",
            "wine_type": "white",
            "tasting_note": "Refined and mineral-driven with crisp apple, citrus, and subtle oak. Exceptional balance and length.",
            "alcohol_content": 13.0
        },
        {
            "producer": "Veuve Clicquot",
            "wine_name": "Yellow Label Brut",
            "region": "Champagne",
            "country": "France",
            "vintage": None,
            "price": 75.00,
            "grapes": "Pinot Noir, Chardonnay, Pinot Meunier",
            "wine_type": "sparkling",
            "tasting_note": "Elegant and vibrant with fine bubbles. Notes of apple, pear, and brioche with a creamy texture.",
            "alcohol_content": 12.0
        },
        {
            "producer": "Chateau d'Yquem",
            "wine_name": "Sauternes",
            "region": "Bordeaux",
            "country": "France",
            "vintage": 2015,
            "price": 325.00,
            "grapes": "Sémillon, Sauvignon Blanc",
            "wine_type": "dessert",
            "tasting_note": "Luscious and complex with honeyed apricot, caramel, and spice. Perfect balance of sweetness and acidity.",
            "alcohol_content": 14.0
        },
        {
            "producer": "Flowers Vineyard",
            "wine_name": "Sonoma Coast Pinot Noir",
            "region": "Sonoma Coast",
            "country": "USA",
            "vintage": 2021,
            "price": 85.00,
            "grapes": "Pinot Noir",
            "wine_type": "red",
            "tasting_note": "Elegant and nuanced with red cherry, earth, and subtle spice. Medium-bodied with silky tannins.",
            "alcohol_content": 13.5
        }
    ]
    
    df = pd.DataFrame(sample_wines)
    
    # Create data/raw directory if it doesn't exist
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    
    output_path = Path("data/raw/sample_wine_list.xlsx")
    df.to_excel(output_path, index=False)
    
    print(f"\n✓ Created sample wine list: {output_path}")
    print(f"  Contains {len(sample_wines)} wines")
    return output_path


def main():
    """Run setup checks and create sample data."""
    print("=" * 60)
    print("Wine Sommelier Agent - Setup & Testing")
    print("=" * 60 + "\n")
    
    # Check environment
    env_ok = check_environment()
    
    if not env_ok:
        print("\n⚠️  Please fix the issues above before proceeding")
        return
    
    # Offer to create sample data
    print("\n" + "=" * 60)
    response = input("Create sample wine list? (y/n): ")
    
    if response.lower() == 'y':
        create_sample_wine_list()
        print("\nNext steps:")
        print("1. Set up Redis (if not running)")
        print("2. Add API keys to .env file")
        print("3. Run: python -c 'from data.wine_data_loader import load_sample_wine_list; load_sample_wine_list()'")
    
    print("\n" + "=" * 60)
    print("Setup complete! See README.md for next steps")
    print("=" * 60)


if __name__ == "__main__":
    main()
