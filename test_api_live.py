"""
Live API Integration Tests
Tests the running FastAPI server endpoints.
Run this while the server is running on http://localhost:8000
"""
import requests
import json
import sys

import os
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = "patscore-8f3k9d2m5p7r"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def test_health():
    """Test /api/v1/health endpoint."""
    print("\n1. Testing GET /api/v1/health...")
    response = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    assert response.status_code == 200
    assert response.json()["ok"] == True
    print("   ✓ PASSED")


def test_settings():
    """Test /api/settings endpoint."""
    print("\n2. Testing GET /api/settings...")
    response = requests.get(f"{BASE_URL}/api/settings")
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert "openaiModel" in data
    assert "promptVersion" in data
    assert data["adminApiKeySet"] == True
    print("   ✓ PASSED")


def test_scores_empty():
    """Test /api/scores endpoint (should be empty initially)."""
    print("\n3. Testing GET /api/scores (empty)...")
    response = requests.get(f"{BASE_URL}/api/scores", headers=HEADERS)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert "items" in data
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pageSize"] == 50
    print("   ✓ PASSED")


def test_scores_auth_required():
    """Test that /api/scores requires authentication."""
    print("\n4. Testing /api/scores without auth (should fail)...")
    response = requests.get(f"{BASE_URL}/api/scores")
    print(f"   Status: {response.status_code}")
    assert response.status_code == 401
    print("   ✓ PASSED (correctly rejected)")


def test_scores_with_filters():
    """Test /api/scores with query parameters."""
    print("\n5. Testing GET /api/scores with filters...")
    params = {
        "page": 1,
        "page_size": 25,
        "relevance": "High",
        "search": "test"
    }
    response = requests.get(f"{BASE_URL}/api/scores", headers=HEADERS, params=params)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Response: {json.dumps(data, indent=2)}")
    assert response.status_code == 200
    assert data["pageSize"] == 25
    print("   ✓ PASSED")


def test_airtable_records():
    """Test legacy /api/v1/records endpoint (Airtable)."""
    print("\n6. Testing GET /api/v1/records (Airtable)...")
    params = {"limit": 5, "offset": 0}
    response = requests.get(f"{BASE_URL}/api/v1/records", headers=HEADERS, params=params)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Total records: {data.get('total', 0)}")
    print(f"   Returned: {len(data.get('records', []))}")
    assert response.status_code == 200
    assert "records" in data
    print("   ✓ PASSED")


def add_test_score_to_db():
    """Add a test score directly to the database for testing."""
    print("\n7. Adding test score to database...")
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    
    from api.db import SessionLocal
    from api.models import Score
    from api.utils.hash import compute_abstract_sha1
    from api.utils.time import utcnow
    
    db = SessionLocal()
    try:
        # Check if test score already exists
        existing = db.query(Score).filter_by(patent_id="TEST2023999999A1").first()
        if existing:
            print("   Test score already exists")
            return
        
        # Create test score
        patent_id = "TEST2023999999A1"
        abstract = "This is a test patent for API validation."
        sha1 = compute_abstract_sha1(patent_id, abstract, "v1.0")
        
        score = Score(
            patent_id=patent_id,
            abstract_sha1=sha1,
            relevance="High",
            subsystem_json='["Detection","AI/Fusion"]',
            title="Test Patent for API",
            abstract=abstract,
            pub_date="2023-10-24",
            source="TEST",
            model_id="gpt-4o-mini",
            prompt_version="v1.0"
        )
        
        db.add(score)
        db.commit()
        print(f"   Added test score: {patent_id}")
        print("   ✓ PASSED")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        db.rollback()
    finally:
        db.close()


def test_scores_with_data():
    """Test /api/scores with actual data."""
    print("\n8. Testing GET /api/scores (with data)...")
    response = requests.get(f"{BASE_URL}/api/scores", headers=HEADERS)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Total scores: {data['total']}")
    if data['total'] > 0:
        print(f"   First item: {data['items'][0]['patentId']}")
        print(f"   Relevance: {data['items'][0]['relevance']}")
    assert response.status_code == 200
    print("   ✓ PASSED")


def test_scores_search():
    """Test /api/scores search functionality."""
    print("\n9. Testing GET /api/scores with search...")
    params = {"search": "TEST"}
    response = requests.get(f"{BASE_URL}/api/scores", headers=HEADERS, params=params)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Found: {data['total']} records matching 'TEST'")
    assert response.status_code == 200
    print("   ✓ PASSED")


def main():
    print("=" * 60)
    print("Live API Integration Tests")
    print("=" * 60)
    print(f"Testing server at: {BASE_URL}")
    print(f"Using API key: {API_KEY[:20]}...")
    
    try:
        # Basic endpoint tests
        test_health()
        test_settings()
        test_scores_empty()
        test_scores_auth_required()
        test_scores_with_filters()
        test_airtable_records()
        
        # Add test data and test with data
        add_test_score_to_db()
        test_scores_with_data()
        test_scores_search()
        
        print("\n" + "=" * 60)
        print("All tests PASSED! ✓")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n✗ Test FAILED: {e}")
        return 1
    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Could not connect to server at", BASE_URL)
        print("Make sure the server is running:")
        print("  python -m uvicorn api.main:app --reload --port 8000")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
