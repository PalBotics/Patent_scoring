"""
Phase 1 Integration Tests
Tests the SQLAlchemy models, DB layer, and new API endpoints.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.db import Base
from api.models import Score, QueueItem, IngestJob
from api.utils.hash import compute_abstract_sha1
from api.utils.time import utcnow, utcnow_iso


# Test Database Setup
TEST_DB_PATH = Path("./data/test_phase1.db")


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    
    engine = create_engine(f"sqlite:///{TEST_DB_PATH}", echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    
    # Cleanup
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


# === Hash Utility Tests ===

def test_compute_abstract_sha1():
    """Test SHA1 hash computation."""
    patent_id = "US2023123456A1"
    abstract = "This is a test abstract with   extra   spaces."
    prompt_version = "v1.0"
    
    hash1 = compute_abstract_sha1(patent_id, abstract, prompt_version)
    
    # Should be a 40-character hex string
    assert len(hash1) == 40
    assert all(c in "0123456789abcdef" for c in hash1)
    
    # Same inputs should produce same hash
    hash2 = compute_abstract_sha1(patent_id, abstract, prompt_version)
    assert hash1 == hash2
    
    # Different patent_id should produce different hash
    hash3 = compute_abstract_sha1("US2023999999A1", abstract, prompt_version)
    assert hash1 != hash3
    
    # Different prompt_version should produce different hash
    hash4 = compute_abstract_sha1(patent_id, abstract, "v2.0")
    assert hash1 != hash4
    
    # Whitespace normalization should work
    abstract_normalized = "This is a test abstract with extra spaces."
    hash5 = compute_abstract_sha1(patent_id, abstract_normalized, prompt_version)
    assert hash1 == hash5


def test_utcnow():
    """Test UTC time utilities."""
    now = utcnow()
    assert now.tzinfo is not None
    
    iso_str = utcnow_iso()
    assert "T" in iso_str
    assert "+" in iso_str or "Z" in iso_str.upper()


# === Model Tests ===

def test_score_model_create(test_session):
    """Test creating a Score record."""
    score = Score(
        patent_id="US2023123456A1",
        abstract_sha1="abc123def456",
        relevance="High",
        subsystem_json='["Detection","AI/Fusion"]',
        title="Test Patent",
        abstract="This is a test abstract.",
        pub_date="2023-05-10",
        source="IPAB",
        model_id="gpt-4o-mini",
        prompt_version="v1.0"
    )
    
    test_session.add(score)
    test_session.commit()
    
    # Retrieve and verify
    retrieved = test_session.query(Score).filter_by(patent_id="US2023123456A1").first()
    assert retrieved is not None
    assert retrieved.relevance == "High"
    assert retrieved.subsystem_json == '["Detection","AI/Fusion"]'
    assert retrieved.model_id == "gpt-4o-mini"
    assert retrieved.scored_at is not None


def test_score_model_composite_pk(test_session):
    """Test that (patent_id, abstract_sha1) is a composite primary key."""
    score1 = Score(
        patent_id="US2023123456A1",
        abstract_sha1="hash1",
        relevance="High"
    )
    test_session.add(score1)
    test_session.commit()
    
    # Same patent_id but different hash should work
    score2 = Score(
        patent_id="US2023123456A1",
        abstract_sha1="hash2",
        relevance="Medium"
    )
    test_session.add(score2)
    test_session.commit()
    
    # Verify both exist
    all_scores = test_session.query(Score).filter_by(patent_id="US2023123456A1").all()
    assert len(all_scores) == 2
    
    # Duplicate (patent_id, abstract_sha1) should fail
    score3 = Score(
        patent_id="US2023123456A1",
        abstract_sha1="hash1",
        relevance="Low"
    )
    test_session.add(score3)
    
    with pytest.raises(Exception):  # IntegrityError
        test_session.commit()
    test_session.rollback()


def test_queue_model_create(test_session):
    """Test creating a QueueItem record."""
    queue_item = QueueItem(
        patent_id="US2023789012A1",
        abstract_sha1="xyz789abc123",
        title="Queued Patent",
        abstract="This patent is queued for scoring.",
        pub_date="2023-06-15",
        source="GRANT",
        status="pending"
    )
    
    test_session.add(queue_item)
    test_session.commit()
    
    # Retrieve and verify
    retrieved = test_session.query(QueueItem).filter_by(patent_id="US2023789012A1").first()
    assert retrieved is not None
    assert retrieved.status == "pending"
    assert retrieved.enqueued_at is not None


def test_queue_model_status_update(test_session):
    """Test updating queue item status."""
    queue_item = QueueItem(
        patent_id="US2023111111A1",
        abstract_sha1="test_hash",
        status="pending"
    )
    test_session.add(queue_item)
    test_session.commit()
    
    # Update status
    queue_item.status = "scored"
    test_session.commit()
    
    # Verify
    retrieved = test_session.query(QueueItem).filter_by(patent_id="US2023111111A1").first()
    assert retrieved.status == "scored"


def test_ingest_job_model_create(test_session):
    """Test creating an IngestJob record."""
    job = IngestJob(
        filename="test_file.xml",
        status="running",
        matched_count=0,
        enqueued_count=0
    )
    
    test_session.add(job)
    test_session.commit()
    
    # Retrieve and verify
    retrieved = test_session.query(IngestJob).filter_by(filename="test_file.xml").first()
    assert retrieved is not None
    assert retrieved.status == "running"
    assert retrieved.started_at is not None
    assert retrieved.completed_at is None
    assert retrieved.id is not None


def test_ingest_job_completion(test_session):
    """Test completing an ingest job."""
    job = IngestJob(
        filename="completed_file.xml",
        status="running",
        matched_count=0,
        enqueued_count=0
    )
    test_session.add(job)
    test_session.commit()
    
    # Complete the job
    job.status = "completed"
    job.matched_count = 150
    job.enqueued_count = 100
    job.completed_at = utcnow()
    test_session.commit()
    
    # Verify
    retrieved = test_session.query(IngestJob).filter_by(filename="completed_file.xml").first()
    assert retrieved.status == "completed"
    assert retrieved.matched_count == 150
    assert retrieved.enqueued_count == 100
    assert retrieved.completed_at is not None


# === API Endpoint Tests ===

def test_api_imports():
    """Test that API modules can be imported."""
    try:
        from api import main, db, models, schemas
        from api.utils import hash, time
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import API modules: {e}")


def test_settings_schema():
    """Test SettingsResponse schema."""
    from api.schemas import SettingsResponse
    
    settings = SettingsResponse(
        openaiModel="gpt-4o-mini",
        promptVersion="v1.0",
        airtableBaseId="appTestBase",
        airtableTableName="Patents",
        adminApiKeySet=True
    )
    
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.prompt_version == "v1.0"
    
    # Test JSON serialization with aliases
    json_data = settings.model_dump(by_alias=True)
    assert json_data["openaiModel"] == "gpt-4o-mini"
    assert json_data["promptVersion"] == "v1.0"


def test_scores_list_schema():
    """Test ScoresListResponse schema."""
    from api.schemas import ScoresListResponse, ScoreListItem
    
    items = [
        ScoreListItem(
            patentId="US2023123456A1",
            abstractSha1="abc123",
            relevance="High",
            subsystem=["Detection", "AI/Fusion"],
            title="Test Patent",
            scoredAt="2023-10-24T12:00:00Z"
        )
    ]
    
    response = ScoresListResponse(
        items=items,
        page=1,
        pageSize=50,
        total=1
    )
    
    assert len(response.items) == 1
    assert response.items[0].patent_id == "US2023123456A1"
    assert response.page_size == 50


# === Integration Test ===

def test_full_workflow(test_session):
    """Test a complete workflow: enqueue -> score -> retrieve."""
    patent_id = "US2023WORKFLOW1"
    abstract = "This is a workflow test patent abstract."
    sha1 = compute_abstract_sha1(patent_id, abstract, "v1.0")
    
    # 1. Add to queue
    queue_item = QueueItem(
        patent_id=patent_id,
        abstract_sha1=sha1,
        title="Workflow Test",
        abstract=abstract,
        status="pending"
    )
    test_session.add(queue_item)
    test_session.commit()
    
    # Verify in queue
    pending = test_session.query(QueueItem).filter_by(status="pending").all()
    assert len(pending) == 1
    
    # 2. "Score" it (simulate scoring)
    score = Score(
        patent_id=patent_id,
        abstract_sha1=sha1,
        relevance="Medium",
        subsystem_json='["Detection"]',
        title="Workflow Test",
        abstract=abstract,
        model_id="gpt-4o-mini",
        prompt_version="v1.0"
    )
    test_session.add(score)
    
    # Update queue status
    queue_item.status = "scored"
    test_session.commit()
    
    # 3. Verify scored
    scored_items = test_session.query(Score).all()
    assert len(scored_items) == 1
    assert scored_items[0].relevance == "Medium"
    
    # Verify queue updated
    queue_item_updated = test_session.query(QueueItem).filter_by(patent_id=patent_id).first()
    assert queue_item_updated.status == "scored"


if __name__ == "__main__":
    print("Running Phase 1 Integration Tests...")
    print("=" * 60)
    
    # Run pytest
    exit_code = pytest.main([__file__, "-v", "--tb=short"])
    
    sys.exit(exit_code)
