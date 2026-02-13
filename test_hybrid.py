"""
Test the FastAPI + Streamlit hybrid architecture.
"""
import requests
import time

def test_hybrid_architecture():
    """Test that FastAPI backend works before running Streamlit."""
    print("\n" + "="*60)
    print("Testing FastAPI + Streamlit Hybrid Architecture")
    print("="*60)

    API_URL = "http://localhost:8000"

    # Test 1: Check API is running
    print("\n[1/3] Checking FastAPI backend...")
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Backend online: {data['message']}")
        else:
            print(f"   ✗ Backend returned {response.status_code}")
            print("\n   Start backend first:")
            print("   python -m uvicorn api.mobile_api:app --port 8000")
            return False
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to backend")
        print("\n   Start backend first:")
        print("   python -m uvicorn api.mobile_api:app --port 8000")
        return False

    # Test 2: Test recommendation endpoint
    print("\n[2/3] Testing recommendation endpoint...")
    query = "Bold red wine for steak"
    start = time.time()

    try:
        response = requests.post(
            f"{API_URL}/api/recommend",
            json={"query": query, "restaurant_id": "maass"},
            timeout=60
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Recommendation successful ({elapsed:.2f}s)")
            print(f"   ✓ Wines returned: {len(data['wines'])}")
            print(f"   ✓ Processing time: {data['processing_time']:.2f}s")

            if data['wines']:
                wine = data['wines'][0]
                print(f"\n   Sample wine:")
                print(f"   - {wine['producer']} {wine.get('wine_name', '')}")
                print(f"   - Region: {wine['region']}")
                print(f"   - Price: ${wine.get('price', wine['price_range'])}")
        else:
            print(f"   ✗ API returned {response.status_code}")
            return False

    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    # Test 3: Test caching (second request should be faster)
    print("\n[3/3] Testing cache performance...")
    start2 = time.time()

    try:
        response2 = requests.post(
            f"{API_URL}/api/recommend",
            json={"query": query, "restaurant_id": "maass"},
            timeout=60
        )
        elapsed2 = time.time() - start2

        if response2.status_code == 200:
            data2 = response2.json()
            speedup = elapsed / elapsed2
            print(f"   ✓ Cached request ({elapsed2:.2f}s)")
            print(f"   ✓ Speedup: {speedup:.1f}x faster")
        else:
            print(f"   ✗ Cached request failed")

    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Summary
    print("\n" + "="*60)
    print("Backend Test Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Keep FastAPI running in Terminal 1")
    print("2. Start Streamlit in Terminal 2:")
    print("   streamlit run restaurants/app_fastapi_hybrid.py")
    print("\n3. Open: http://localhost:8501")
    print("="*60 + "\n")

    return True


if __name__ == "__main__":
    test_hybrid_architecture()
