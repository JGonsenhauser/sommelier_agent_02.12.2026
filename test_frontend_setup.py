#!/usr/bin/env python3
"""
Quick frontend setup verification script.
Checks all prerequisites before testing the frontend.
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)

def print_status(status, message):
    symbols = {"pass": "[OK]", "fail": "[X]", "warn": "[!]"}
    colors = {"pass": "\033[92m", "fail": "\033[91m", "warn": "\033[93m"}
    reset = "\033[0m"
    symbol = symbols.get(status, "•")
    color = colors.get(status, "")
    print(f"{color}  {symbol} {message}{reset}")

def check_env_file():
    """Check if .env file exists and has required variables."""
    print_header("1. Environment Variables")

    env_path = Path(".env")
    if not env_path.exists():
        print_status("fail", ".env file not found")
        return False

    print_status("pass", ".env file found")

    # Read and check required variables
    required_vars = [
        "XAI_API_KEY",
        "ENCRYPTION_KEY",
        "XAI_CHAT_MODEL",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME",
        "PINECONE_HOST"
    ]

    env_content = env_path.read_text()
    missing_vars = []

    for var in required_vars:
        if var in env_content and env_content.split(f"{var}=")[1].split("\n")[0].strip():
            print_status("pass", f"{var} is set")
        else:
            print_status("fail", f"{var} is missing or empty")
            missing_vars.append(var)

    if missing_vars:
        print(f"\n  Missing variables: {', '.join(missing_vars)}")
        return False

    return True

def check_dependencies():
    """Check if required packages are installed."""
    print_header("2. Python Dependencies")

    required_packages = {
        "openai": "openai",
        "fastapi": "fastapi",
        "streamlit": "streamlit",
        "uvicorn": "uvicorn",
        "pinecone": "pinecone",
        "cryptography": "cryptography",
        "redis": "redis",
        "qrcode": "qrcode",
        "python-dotenv": "dotenv"  # Package name vs import name
    }

    all_installed = True
    for package, import_name in required_packages.items():
        try:
            __import__(import_name.replace("-", "_"))
            print_status("pass", f"{package} installed")
        except ImportError:
            print_status("fail", f"{package} not installed")
            all_installed = False

    if not all_installed:
        print("\n  Install missing packages:")
        print("  pip install -r requirements.txt")
        return False

    return True

def check_config():
    """Check if config.py loads correctly."""
    print_header("3. Configuration Loading")

    try:
        from config import settings
        print_status("pass", "config.py loaded successfully")

        # Check XAI settings
        if settings.xai_chat_model:
            print_status("pass", f"XAI chat model: {settings.xai_chat_model}")
        else:
            print_status("fail", "XAI chat model not configured")
            return False

        # Try to decrypt XAI key
        try:
            decrypted_key = settings.get_decrypted_xai_key()
            if decrypted_key and len(decrypted_key) > 10:
                print_status("pass", f"XAI API key decrypted (length: {len(decrypted_key)})")
            else:
                print_status("fail", "XAI API key is empty or invalid")
                return False
        except Exception as e:
            print_status("fail", f"Failed to decrypt XAI key: {e}")
            return False

        return True

    except Exception as e:
        print_status("fail", f"Error loading config: {e}")
        return False

def check_xai_connection():
    """Test XAI Grok API connection."""
    print_header("4. XAI Grok API Connection")

    try:
        from openai import OpenAI
        from config import settings

        xai_api_key = settings.get_decrypted_xai_key()
        client = OpenAI(
            api_key=xai_api_key,
            base_url="https://api.x.ai/v1"
        )

        # Test API call
        response = client.chat.completions.create(
            model=settings.xai_chat_model,
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            max_tokens=20
        )

        result = response.choices[0].message.content
        print_status("pass", "XAI Grok API connected successfully")
        print_status("pass", f"Model: {settings.xai_chat_model}")
        print_status("pass", f"Response: {result[:50]}...")
        return True

    except Exception as e:
        print_status("fail", f"XAI API connection failed: {e}")
        print("\n  Troubleshooting:")
        print("  1. Check XAI_API_KEY in .env")
        print("  2. Verify key at: https://console.x.ai/")
        print("  3. Check internet connection")
        return False

def check_pinecone_connection():
    """Test Pinecone connection and data."""
    print_header("5. Pinecone Vector Database")

    try:
        from pinecone import Pinecone
        from config import settings

        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index_name, host=settings.pinecone_host)

        print_status("pass", "Pinecone connected")
        print_status("pass", f"Index: {settings.pinecone_index_name}")

        # Check stats
        stats = index.describe_index_stats()
        total_vectors = stats.get('total_vector_count', 0)

        if total_vectors > 0:
            print_status("pass", f"Total vectors: {total_vectors}")
        else:
            print_status("warn", "No vectors in index - need to run data ingestion")
            print("\n  Run: python embed_maass_schema_v2.py")
            return False

        # Check maass_wine_list namespace (correct namespace from restaurant_config)
        namespaces = stats.get('namespaces', {})
        if 'maass_wine_list' in namespaces:
            maass_count = namespaces['maass_wine_list'].get('vector_count', 0)
            print_status("pass", f"MAASS namespace: {maass_count} wines")
        else:
            print_status("warn", "MAASS namespace 'maass_wine_list' not found")
            print(f"\n  Available namespaces: {list(namespaces.keys())}")
            return False

        return True

    except Exception as e:
        print_status("fail", f"Pinecone connection failed: {e}")
        print("\n  Troubleshooting:")
        print("  1. Check PINECONE_API_KEY in .env")
        print("  2. Verify PINECONE_HOST is correct")
        print("  3. Check index exists at: https://app.pinecone.io/")
        return False

def check_redis():
    """Check Redis connection (optional)."""
    print_header("6. Redis Cache (Optional)")

    try:
        import redis
        import os

        # Check for REDIS_URL first (Redis Cloud, Railway, etc.)
        redis_url = os.getenv('REDIS_URL')

        if redis_url:
            client = redis.from_url(redis_url, socket_connect_timeout=5)
            client.ping()
            print_status("pass", "Redis Cloud connected")
            print_status("pass", f"Using: {redis_url.split('@')[1] if '@' in redis_url else 'Redis Cloud'}")
            print_status("pass", "Persistent cache enabled (10-50x faster cached responses)")
            return True
        else:
            # Fallback to localhost
            client = redis.Redis(host='localhost', port=6379, db=0, socket_connect_timeout=2)
            client.ping()
            print_status("pass", "Local Redis connected")
            print_status("pass", "Caching enabled (fast responses)")
            return True
    except Exception as e:
        print_status("warn", "Redis not running (will use in-memory cache)")
        print("\n  Redis is optional but recommended for production")
        print("  To add Redis Cloud: See REDIS_SETUP_GUIDE.md")
        return False

def check_files():
    """Check if required files exist."""
    print_header("7. Required Files")

    required_files = [
        "api/mobile_api.py",
        "restaurants/app_fastapi_hybrid.py",
        "restaurants/restaurant_config.py",
        "restaurants/wine_recommender_optimized.py",
        "config.py",
        "requirements.txt",
        ".streamlit/config.toml"
    ]

    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print_status("pass", file_path)
        else:
            print_status("fail", f"{file_path} not found")
            all_exist = False

    return all_exist

def print_next_steps(all_passed):
    """Print next steps based on test results."""
    print_header("Test Results")

    if all_passed:
        print_status("pass", "All checks passed! Ready to test frontend")
        print("\n" + "="*60)
        print("  >>> NEXT STEPS")
        print("="*60)
        print("\n  Terminal 1 - Start Backend:")
        print("  python -m uvicorn api.mobile_api:app --reload --port 8000")
        print("\n  Terminal 2 - Test Backend:")
        print("  python test_hybrid.py")
        print("\n  Terminal 3 - Start Frontend:")
        print("  streamlit run restaurants/app_fastapi_hybrid.py")
        print("\n  Then open: http://localhost:8501")
        print("\n  >>> Full guide: FRONTEND_TESTING_GUIDE.md")
        print("="*60 + "\n")
    else:
        print_status("fail", "Some checks failed - fix issues before testing")
        print("\n" + "="*60)
        print("  >>> FIX ISSUES FIRST")
        print("="*60)
        print("\n  1. Review error messages above")
        print("  2. Fix configuration issues")
        print("  3. Run this script again")
        print("\n  >>> See: FRONTEND_TESTING_GUIDE.md for troubleshooting")
        print("="*60 + "\n")

def main():
    """Run all checks."""
    print("\n" + "="*60)
    print("  >>> Frontend Setup Verification")
    print("="*60)
    print("\n  This script checks if your environment is ready for testing.")
    print("  It will verify:")
    print("  • Environment variables")
    print("  • Python dependencies")
    print("  • API connections (XAI, Pinecone)")
    print("  • Required files")

    checks = [
        ("Environment", check_env_file),
        ("Dependencies", check_dependencies),
        ("Config", check_config),
        ("XAI API", check_xai_connection),
        ("Pinecone", check_pinecone_connection),
        ("Files", check_files),
        ("Redis", check_redis)  # Optional
    ]

    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print_status("fail", f"{name} check failed: {e}")
            results.append(False)

    # Redis is optional, don't fail on it
    all_passed = all(results[:-1])  # Exclude Redis from required checks

    print_next_steps(all_passed)

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
