import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables from .env file
load_dotenv()

import pytest
from fastapi.testclient import TestClient
from api.schemas import RecordSummary, RecordDetail, ListRecordsResponse, ScoreRequest

# Use the API key from .env
API_KEY = os.getenv("APP_API_KEY")
if not API_KEY:
    raise ValueError("APP_API_KEY must be set in .env file")

# Import app after environment is set up
from api.main import app

@pytest.fixture(scope="session")
def test_db():
    """Create a test database and tables"""
    db_path = "test_patent_scores.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patent_scores (
            id TEXT PRIMARY KEY,
            patent_id TEXT,
            title TEXT,
            abstract TEXT,
            relevance TEXT,
            score INTEGER,
            subsystem TEXT,
            sha1 TEXT,
            updated_at TIMESTAMP,
            provenance TEXT
        )
    """)
    
    # Add some test data
    cur.execute("""
        INSERT OR REPLACE INTO patent_scores (
            id, patent_id, title, abstract, relevance, score, subsystem, sha1, updated_at
        ) VALUES (
            'test1', 'PAT123', 'Test Patent', 'Test abstract', 'Medium', 75, 
            '["Detection", "AI"]', 'abc123', CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    
    yield conn  # provide the connection to tests
    
    # Cleanup after tests
    conn.close()
    try:
        os.remove(db_path)
    except:
        pass  # ignore errors on cleanup

# Create a fresh test client for each test
@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {API_KEY}"}

def test_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

def test_auth_required(client):
    resp = client.get("/api/v1/records")
    print(f"Auth test response: {resp.status_code}, {resp.json()}")
    assert resp.status_code == 401
    assert "Authorization" in resp.json()["detail"] or "API key" in resp.json()["detail"]

def test_list_records(client, headers, test_db):
    resp = client.get("/api/v1/records", headers=headers)
    print(f"List records response: {resp.status_code}, {resp.json()}")
    assert resp.status_code == 200
    data = resp.json()
    assert "records" in data
    assert isinstance(data["records"], list)
    assert len(data["records"]) > 0
    assert data["records"][0]["patent_id"] == "PAT123"  # Check our test data

def test_score_record_keyword(client, headers):
    payload = {
        "title": "Test patent title",
        "abstract": "Test abstract about detection and AI.",
        "mode": "keyword",
        "mapping": {"Detection": ["detect"], "AI": ["ai"]}
    }
    resp = client.post("/api/v1/score", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["relevance"] in ["Low", "Medium", "High"]
    assert isinstance(data["score"], int)
    assert isinstance(data["subsystem"], list)
    assert "sha1" in data
    assert "provenance" in data
