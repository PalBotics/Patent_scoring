from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class RecordSummary(BaseModel):
    id: str
    patent_id: str
    title: str
    abstract: Optional[str] = None
    relevance: Optional[str] = None  # "Low"|"Medium"|"High"|None
    score: Optional[int] = None
    subsystem: Optional[List[str]] = None
    sha1: str
    updated_at: Optional[datetime] = None

class Provenance(BaseModel):
    method: str  # "llm"|"keyword"|"cached"
    prompt_version: Optional[str] = None
    scored_at: Optional[datetime] = None
    airtable_id: Optional[str] = None
    model: Optional[str] = None
    openai_response_id: Optional[str] = None

class RecordDetail(RecordSummary):
    provenance: Optional[Provenance] = None

class ScoreRequest(BaseModel):
    title: str
    abstract: str
    record_id: Optional[str] = None
    mapping: Optional[Dict[str, List[str]]] = None
    mode: Optional[str] = Field(default="llm", description="llm or keyword")

class ScoreResponse(BaseModel):
    relevance: str
    score: int
    subsystem: List[str]
    sha1: str
    provenance: Provenance

class ListRecordsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    records: List[RecordSummary]

class ErrorResponse(BaseModel):
    detail: str
