"""
SQLAlchemy ORM models for the patent scoring system.
Implements three tables: scores, queue, and ingest_jobs per the spec.
"""
from sqlalchemy import Column, Integer, Text, String, DateTime, Index
from sqlalchemy.sql import func
from api.db import Base


class Score(Base):
    """
    Results cache for scored patents.
    PK: (patent_id, abstract_sha1)
    """
    __tablename__ = "scores"

    patent_id = Column(Text, primary_key=True, nullable=False)
    abstract_sha1 = Column(Text, primary_key=True, nullable=False)
    relevance = Column(Text, nullable=True)  # "High" | "Medium" | "Low"
    subsystem_json = Column(Text, nullable=True)  # JSON array as text
    title = Column(Text, nullable=True)
    abstract = Column(Text, nullable=True)
    pub_date = Column(Text, nullable=True)  # YYYYMMDD or YYYY-MM-DD
    source = Column(Text, nullable=True)  # IPAB | GRANT | XML
    model_id = Column(Text, nullable=True)  # e.g., gpt-4o-mini
    prompt_version = Column(Text, nullable=True)  # e.g., v1.0
    scored_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_scores_relevance", "relevance"),
        Index("idx_scores_pub_date", "pub_date"),
    )


class QueueItem(Base):
    """
    Queue of patents to be scored.
    PK: (patent_id, abstract_sha1)
    """
    __tablename__ = "queue"

    patent_id = Column(Text, primary_key=True, nullable=False)
    abstract_sha1 = Column(Text, primary_key=True, nullable=False)
    title = Column(Text, nullable=True)
    abstract = Column(Text, nullable=True)
    pub_date = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    enqueued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(Text, nullable=False, default="pending")  # pending | scored | skipped

    __table_args__ = (
        Index("idx_queue_status", "status"),
    )


class IngestJob(Base):
    """
    Upload/parse job status tracking.
    """
    __tablename__ = "ingest_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Text, nullable=False, default="running")  # running | completed | failed
    matched_count = Column(Integer, nullable=False, default=0)
    enqueued_count = Column(Integer, nullable=False, default=0)
    log = Column(Text, nullable=True)  # Short error/status message
