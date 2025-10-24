from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# --- Existing schemas (updated to match spec) ---

class RecordSummary(BaseModel):
    """Summary of a scored patent record (legacy endpoint compatibility)."""
    id: Optional[str] = None  # Airtable record ID for legacy endpoint
    patent_id: str = Field(..., alias="patentId")
    abstract_sha1: Optional[str] = Field(None, alias="abstractSha1")
    title: Optional[str] = None
    abstract: Optional[str] = None
    relevance: Optional[str] = None  # "High" | "Medium" | "Low"
    subsystem: List[str] = Field(default_factory=list)
    pub_date: Optional[str] = Field(None, alias="pubDate")
    source: Optional[str] = None  # IPAB | GRANT | XML
    scored_at: Optional[str] = Field(None, alias="scoredAt")
    sha1: Optional[str] = None  # Legacy field
    updated_at: Optional[str] = None  # Legacy field
    score: Optional[int] = None  # Legacy field

    class Config:
        populate_by_name = True


class Provenance(BaseModel):
    """Scoring provenance metadata."""
    method: str  # "llm" | "keyword" | "cached"
    prompt_version: Optional[str] = None
    scored_at: Optional[datetime] = None
    model_id: Optional[str] = Field(None, alias="modelId")

    class Config:
        populate_by_name = True


class RecordDetail(RecordSummary):
    """Detailed record with provenance."""
    provenance: Optional[Provenance] = None


class ScoreRequest(BaseModel):
    """Request to score a single patent."""
    title: str
    abstract: str
    patent_id: Optional[str] = Field(None, alias="patentId")
    mapping: Optional[Dict[str, List[str]]] = None
    mode: Optional[str] = Field(default="llm", description="llm or keyword")

    class Config:
        populate_by_name = True


class ScoreResponse(BaseModel):
    """Response from scoring endpoint."""
    relevance: str  # "High" | "Medium" | "Low"
    subsystem: List[str]
    sha1: str

    class Config:
        populate_by_name = True


class ListRecordsResponse(BaseModel):
    """Paginated list of records (legacy endpoint)."""
    total: int
    offset: int
    limit: int
    records: List[RecordSummary]


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


# --- New spec schemas ---

class ScoreListItem(BaseModel):
    """Item in the scores list (GET /api/scores)."""
    patent_id: str = Field(..., alias="patentId")
    abstract_sha1: str = Field(..., alias="abstractSha1")
    relevance: str
    subsystem: List[str]
    title: Optional[str] = None
    abstract: Optional[str] = None
    pub_date: Optional[str] = Field(None, alias="pubDate")
    source: Optional[str] = None
    scored_at: str = Field(..., alias="scoredAt")

    class Config:
        populate_by_name = True


class ScoresListResponse(BaseModel):
    """Response for GET /api/scores."""
    items: List[ScoreListItem]
    page: int
    page_size: int = Field(..., alias="pageSize")
    total: int

    class Config:
        populate_by_name = True


class QueueListItem(BaseModel):
    """Item in the queue list (GET /api/queue)."""
    patent_id: str = Field(..., alias="patentId")
    abstract_sha1: str = Field(..., alias="abstractSha1")
    title: Optional[str] = None
    abstract: Optional[str] = None
    pub_date: Optional[str] = Field(None, alias="pubDate")
    source: Optional[str] = None
    status: str  # pending | scored | skipped
    enqueued_at: str = Field(..., alias="enqueuedAt")

    class Config:
        populate_by_name = True


class QueueListResponse(BaseModel):
    """Response for GET /api/queue."""
    items: List[QueueListItem]
    page: int
    page_size: int = Field(..., alias="pageSize")
    total: int

    class Config:
        populate_by_name = True


class SettingsResponse(BaseModel):
    """Response for GET /api/settings."""
    openai_model: str = Field(..., alias="openaiModel")
    prompt_version: str = Field(..., alias="promptVersion")
    airtable_base_id: str = Field(..., alias="airtableBaseId")
    airtable_table_name: str = Field(..., alias="airtableTableName")
    admin_api_key_set: bool = Field(..., alias="adminApiKeySet")

    class Config:
        populate_by_name = True


class IngestJobResponse(BaseModel):
    """Response for ingest job status (GET /api/ingest/{jobId})."""
    job_id: int = Field(..., alias="jobId")
    filename: Optional[str] = None
    status: str  # running | completed | failed
    matched_count: int = Field(..., alias="matchedCount")
    enqueued_count: int = Field(..., alias="enqueuedCount")
    csv_url: Optional[str] = Field(None, alias="csvUrl")
    log: Optional[str] = None

    class Config:
        populate_by_name = True