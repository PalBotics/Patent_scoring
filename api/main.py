import os
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from api.schemas import (
    ErrorResponse,
    ListRecordsResponse,
    Provenance,
    QueueListItem,
    QueueListResponse,
    RecordDetail,
    RecordSummary,
    ScoreListItem,
    ScoreRequest,
    ScoreResponse,
    ScoresListResponse,
    SettingsResponse,
    IngestJobResponse,
)
from api.db import get_db, init_db as init_database
from api import airtable_service
import scorer

load_dotenv()

# Initialize database on startup
init_database()

API_KEY = os.getenv("APP_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1.0")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Patents")

# Security scheme for Swagger UI
security = HTTPBearer()

app = FastAPI(title="Patent Scoring API", version="0.1.0")

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: APP_API_KEY not set.")
    if credentials.credentials != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials


@app.get("/api/v1/records", response_model=ListRecordsResponse)
async def list_records(
    limit: int = 25,
    offset: int = 0,
    q: Optional[str] = None,
    relevance: Optional[str] = None,
    subsystem: Optional[str] = None,
    api_key: str = Depends(get_api_key),
):
    try:
        # Fetch windowed records from Airtable
        records, total = airtable_service.fetch_records(limit=limit, offset=offset)

        record_list: List[RecordSummary] = []
        for rec in records:
            raw_subsystem = rec.get("subsystem", [])
            if raw_subsystem is None:
                subsys: List[str] = []
            elif isinstance(raw_subsystem, str):
                subsys = [raw_subsystem]
            elif isinstance(raw_subsystem, list):
                subsys = [str(x) for x in raw_subsystem if x is not None]
            else:
                subsys = []

            pub_date_val = rec.get("pub_date", "")
            pub_date_str = str(pub_date_val) if pub_date_val is not None else ""

            record_list.append(
                RecordSummary(
                    id=rec.get("id", ""),
                    patent_id=rec.get("patent_id", ""),
                    abstract_sha1=None,
                    title=rec.get("title", ""),
                    abstract=rec.get("abstract", ""),
                    relevance=rec.get("relevance"),
                    score=0,  # Legacy convenience field
                    subsystem=subsys,
                    sha1="",
                    updated_at=pub_date_str,
                )
            )

        return ListRecordsResponse(total=total, offset=offset, limit=limit, records=record_list)
    except Exception as e:
        import traceback
        print("Error in list_records:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Airtable error: {str(e)}")


@app.get("/api/v1/records/{record_id}", response_model=RecordDetail)
async def get_record(record_id: str, api_key: str = Depends(get_api_key)):
    """Fetch a single record from Airtable by record ID."""
    try:
        import requests
        
        if not (airtable_service.AIRTABLE_API_KEY and airtable_service.AIRTABLE_BASE_ID and airtable_service.AIRTABLE_TABLE_NAME):
            raise HTTPException(status_code=500, detail="Airtable not configured")
        
        url = f"https://api.airtable.com/v0/{airtable_service.AIRTABLE_BASE_ID}/{airtable_service.AIRTABLE_TABLE_NAME}/{record_id}"
        headers = airtable_service._base_headers()
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Record {record_id} not found")
        
        response.raise_for_status()
        data = response.json()
        
        # Normalize the single record
        normalized = airtable_service._normalize_record(data)
        
        # Convert to RecordDetail schema
        raw_subsystem = normalized.get("subsystem", [])
        if raw_subsystem is None:
            subsys: List[str] = []
        elif isinstance(raw_subsystem, str):
            subsys = [raw_subsystem]
        elif isinstance(raw_subsystem, list):
            subsys = [str(x) for x in raw_subsystem if x is not None]
        else:
            subsys = []
        
        pub_date_val = normalized.get("pub_date", "")
        pub_date_str = str(pub_date_val) if pub_date_val is not None else ""
        
        return RecordDetail(
            id=normalized.get("id", ""),
            patent_id=normalized.get("patent_id", ""),
            abstract_sha1=None,
            title=normalized.get("title", ""),
            abstract=normalized.get("abstract", ""),
            relevance=normalized.get("relevance"),
            score=0,
            subsystem=subsys,
            sha1="",
            updated_at=pub_date_str,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in get_record: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching record: {str(e)}")


@app.post("/api/v1/score", response_model=ScoreResponse)
async def score_record(req: ScoreRequest, api_key: str = Depends(get_api_key)):
    try:
        # Use keyword scorer for now; LLM integration to be added
        result = scorer.keyword_score(title=req.title, abstract=req.abstract, mapping=req.mapping or {})
        prov = Provenance(method=("keyword" if req.mode == "keyword" else "llm"), prompt_version=os.getenv("PROMPT_VERSION"), scored_at=datetime.utcnow())

        return ScoreResponse(
            relevance=str(result.get("relevance", "Low")),
            score=int(result.get("score", 0)),
            subsystem=list(result.get("subsystem", [])),
            sha1=str(result.get("sha1", "")),
            provenance=prov,
        )
    except Exception as e:
        print(f"Error in score_record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scoring error: {str(e)}")


@app.get("/api/v1/health")
def health():
    return {"ok": True, "version": "0.1.0"}


# --- New spec endpoints ---


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(
        openaiModel=OPENAI_MODEL,
        promptVersion=PROMPT_VERSION,
        airtableBaseId=AIRTABLE_BASE_ID if AIRTABLE_BASE_ID else "not-set",
        airtableTableName=AIRTABLE_TABLE_NAME,
        adminApiKeySet=bool(API_KEY),
    )


@app.get("/api/scores", response_model=ScoresListResponse)
async def list_scores(
    page: int = 1,
    page_size: int = 50,
    relevance: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    from api.models import Score
    from sqlalchemy import or_

    query = db.query(Score)

    if relevance:
        query = query.filter(Score.relevance == relevance)
    if source:
        query = query.filter(Score.source == source)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Score.title.ilike(search_term),
                Score.abstract.ilike(search_term),
                Score.patent_id.ilike(search_term),
            )
        )

    total = query.count()

    offset_val = (page - 1) * page_size
    items_db = query.order_by(Score.scored_at.desc()).offset(offset_val).limit(page_size).all()

    items = [
        ScoreListItem(
            patentId=item.patent_id,
            abstractSha1=item.abstract_sha1,
            relevance=item.relevance or "Low",
            subsystem=(eval(item.subsystem_json) if item.subsystem_json else []),
            title=item.title,
            abstract=item.abstract,
            pubDate=item.pub_date,
            source=item.source,
            scoredAt=item.scored_at.isoformat() if item.scored_at else "",
        )
        for item in items_db
    ]

    return ScoresListResponse(items=items, page=page, pageSize=page_size, total=total)


@app.get("/api/queue", response_model=QueueListResponse)
def get_queue(
    page: int = 1,
    page_size: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    from api.models import QueueItem

    query = db.query(QueueItem)
    if status:
        query = query.filter(QueueItem.status == status)

    query = query.order_by(QueueItem.enqueued_at.desc())

    total = query.count()
    offset_val = (page - 1) * page_size
    items_db = query.offset(offset_val).limit(page_size).all()

    items = [
        QueueListItem(
            patentId=item.patent_id,
            abstractSha1=item.abstract_sha1,
            title=item.title,
            abstract=item.abstract,
            pubDate=item.pub_date,
            source=item.source,
            status=item.status,
            enqueuedAt=item.enqueued_at.isoformat() if item.enqueued_at else "",
        )
        for item in items_db
    ]

    return QueueListResponse(items=items, page=page, pageSize=page_size, total=total)


@app.post("/api/queue/skip")
def skip_queue_items(
    patent_ids: List[str],
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    from api.models import QueueItem

    updated = (
        db.query(QueueItem)
        .filter(QueueItem.patent_id.in_(patent_ids))
        .update({QueueItem.status: "skipped"}, synchronize_session=False)
    )

    db.commit()

    return {"updated": updated, "patentIds": patent_ids}


# --- Ingest endpoints ---

@app.post("/api/ingest", response_model=IngestJobResponse)
def start_ingest(
    filename: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """Start an ingest job (stub)."""
    from api.models import IngestJob

    job = IngestJob(filename=filename or "upload.csv", status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    return IngestJobResponse(
        jobId=job.id,
        filename=job.filename,
        status=job.status,
        matchedCount=job.matched_count,
        enqueuedCount=job.enqueued_count,
        csvUrl=None,
        log=job.log,
    )


@app.get("/api/ingest/{job_id}", response_model=IngestJobResponse)
def get_ingest_job(
    job_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    from api.models import IngestJob

    job = db.query(IngestJob).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Ingest job not found")

    return IngestJobResponse(
        jobId=job.id,
        filename=job.filename,
        status=job.status,
        matchedCount=job.matched_count,
        enqueuedCount=job.enqueued_count,
        csvUrl=None,
        log=job.log,
    )
