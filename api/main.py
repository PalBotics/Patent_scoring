import os
from datetime import datetime
from typing import List, Optional
import tempfile
import shutil
import json
import logging
from pathlib import Path
import urllib.parse

from fastapi import Depends, FastAPI, Header, HTTPException, Security, UploadFile, File, BackgroundTasks
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

# Module logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

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
        # Fetch windowed records from Airtable with filters
        records, total = airtable_service.fetch_records(limit=limit, offset=offset, q=q, relevance=relevance, subsystem=subsystem)
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


# Compatibility aliases for health/settings to match potential frontend expectations
@app.get("/health")
def health_alias_root():
    return {"ok": True, "version": "0.1.0"}


@app.get("/api/health")
def health_alias_api():
    return {"ok": True, "version": "0.1.0"}


@app.get("/api/stats")
def get_stats(
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """Get real-time counts for queue and scores."""
    from api.models import QueueItem, Score
    
    pending_count = db.query(QueueItem).filter(QueueItem.status == "pending").count()
    scored_in_queue = db.query(QueueItem).filter(QueueItem.status == "scored").count()
    total_queue = db.query(QueueItem).count()
    total_scores = db.query(Score).count()
    
    return {
        "queue": {
            "pending": pending_count,
            "scored": scored_in_queue,
            "total": total_queue,
        },
        "scores": {
            "total": total_scores,
        }
    }


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


# Alias without "/api" prefix for clients that call /settings
@app.get("/settings", response_model=SettingsResponse)
async def get_settings_alias():
    return await get_settings()


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
    from api.models import QueueItem, Score

    # Join QueueItem with Score to get the relevance score if it exists
    query = db.query(QueueItem, Score.relevance).outerjoin(
        Score,
        (QueueItem.patent_id == Score.patent_id) & 
        (QueueItem.abstract_sha1 == Score.abstract_sha1)
    )
    
    if status:
        query = query.filter(QueueItem.status == status)

    query = query.order_by(QueueItem.enqueued_at.desc())

    total = query.count()
    offset_val = (page - 1) * page_size
    results = query.offset(offset_val).limit(page_size).all()

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
            score=score if score else None,
        )
        for item, score in results
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
async def start_ingest(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Upload and ingest USPTO file (CSV, XML, XML.GZ, or ZIP).
    Parses file, deduplicates against scores DB, queues new patents for scoring.
    """
    from api.models import IngestJob
    from api.ingest_service import process_ingest_job
    
    # Validate file type
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ['.csv', '.xml', '.gz', '.zip']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: .csv, .xml, .gz, .zip"
        )
    
    # Create ingest job
    job = IngestJob(filename=filename, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Save uploaded file temporarily
    temp_dir = Path(tempfile.gettempdir()) / "patent_ingest"
    temp_dir.mkdir(exist_ok=True)
    temp_file = temp_dir / f"job_{job.id}_{filename}"
    
    try:
        with open(temp_file, 'wb') as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        job.status = 'failed'
        job.log = f"File upload failed: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    
    # Process in background
    background_tasks.add_task(process_ingest_job, job.id, str(temp_file))
    
    return IngestJobResponse(
        jobId=job.id,
        filename=job.filename,
        status=job.status,
        matchedCount=0,
        enqueuedCount=0,
        csvUrl=None,
        log="Processing started",
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






# --- Batch Scoring endpoints ---

@app.post("/api/queue/process-batch")
async def process_scoring_batch(
    background_tasks: BackgroundTasks,
    batch_size: int = 10,
    mode: str = "keyword",
    min_relevance: str = "Medium",
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Process a batch of pending patents from queue.
    Scores them and stores Medium/High relevance results.
    """
    from api.scoring_service import process_queue_batch
    
    # Run in background
    background_tasks.add_task(
        process_queue_batch,
        batch_size=batch_size,
        mode=mode,
        min_relevance=min_relevance
    )
    
    return {
        "ok": True,
        "message": f"Processing batch of {batch_size} patents in background"
    }


@app.post("/api/queue/process-all")
async def process_all_pending(
    background_tasks: BackgroundTasks,
    mode: str = "keyword",
    min_relevance: str = "Medium",
    batch_size: int = 10,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key),
):
    """
    Process all pending patents in queue.
    Continues until queue is empty.
    """
    from api.scoring_service import process_all_pending as process_all
    
    # Run in background
    background_tasks.add_task(
        process_all,
        mode=mode,
        min_relevance=min_relevance,
        batch_size=batch_size
    )
    
    return {
        "ok": True,
        "message": "Processing all pending patents in background"
    }


# --- Airtable Sync endpoint ---

from pydantic import BaseModel

class SyncRequest(BaseModel):
    patent_ids: List[str]

@app.post("/api/sync-airtable")
def sync_to_airtable(
    request: SyncRequest,
    api_key: str = Depends(get_api_key),
):
    """
    Sync selected scored patents to Airtable (synchronous).
    - Only syncs High/Medium scored items from the provided patent_ids.
    - Removes Low-scored items from the queue for those ids.
    Returns a summary of actions.
    """
    from api import airtable_service
    from api.models import Score, QueueItem
    from api.db import SessionLocal

    patent_ids = request.patent_ids or []
    db = SessionLocal()
    try:
        if not patent_ids:
            return {"ok": False, "message": "No patent_ids provided", "synced": 0, "skipped": 0, "errors": 0, "removed": 0}

        # Get High/Medium scores for the selected patent_ids
        scores = (
            db.query(Score)
            .filter(Score.patent_id.in_(patent_ids), Score.relevance.in_(["High", "Medium"]))
            .all()
        )

        synced = 0
        skipped = 0
        errors = 0
        details: List[dict] = []

        import requests

        for score in scores:
            try:
                # Prepare Airtable fields (using Airtable's field names)
                subsystem = json.loads(score.subsystem_json) if getattr(score, "subsystem_json", None) else []
                fields = {
                    "Patent ID": score.patent_id,
                    "Abstract": getattr(score, "abstract", "") or "",
                    "Relevance": score.relevance,
                    # To avoid Airtable 422 INVALID_MULTIPLE_CHOICE_OPTIONS when options are not pre-defined
                    # in the base (and API token cannot create them), omit values and send an empty list.
                    # If needed, we can later update this to filter against a configured allowlist.
                    "Subsystem": [],
                    "Publication Date": getattr(score, "pub_date", "") or "",
                }
                # Do NOT include Title unless the Airtable schema has that field.
                # Current base does not include a Title field, so we omit it to avoid 422 UNKNOWN_FIELD_NAME.

                # Check for existing by Patent ID using filterByFormula
                base = airtable_service.AIRTABLE_BASE_ID
                table = airtable_service.AIRTABLE_TABLE_NAME
                headers = airtable_service._base_headers()
                formula = urllib.parse.quote("{Patent ID}='" + score.patent_id.replace("'", "\\'") + "'")
                list_url = f"https://api.airtable.com/v0/{base}/{table}?maxRecords=1&filterByFormula={formula}"
                list_resp = requests.get(list_url, headers=headers)
                if list_resp.ok and list_resp.json().get("records"):
                    logger.info(f"Skipping {score.patent_id} - already in Airtable")
                    skipped += 1
                    details.append({
                        "patent_id": score.patent_id,
                        "status": "skipped",
                        "reason": "already exists"
                    })
                    continue

                # Create record
                create_url = f"https://api.airtable.com/v0/{base}/{table}"
                create_resp = requests.post(create_url, headers=headers, json={"fields": fields})
                if create_resp.ok:
                    logger.info(f"Synced {score.patent_id} to Airtable")
                    synced += 1
                    at_id = None
                    try:
                        at_id = create_resp.json().get("id")
                    except Exception:
                        pass
                    details.append({
                        "patent_id": score.patent_id,
                        "status": "synced",
                        "airtable_id": at_id
                    })
                else:
                    err_text = None
                    try:
                        err_text = create_resp.text
                    except Exception:
                        err_text = None
                    logger.error(
                        f"Failed to sync {score.patent_id}: {create_resp.status_code} - {err_text}"
                    )
                    errors += 1
                    details.append({
                        "patent_id": score.patent_id,
                        "status": "error",
                        "code": create_resp.status_code,
                        "error": (err_text[:300] if isinstance(err_text, str) else None)
                    })
            except Exception as e:
                logger.error(f"Sync error for {getattr(score, 'patent_id', '?')}: {e}")
                errors += 1
                details.append({
                    "patent_id": getattr(score, 'patent_id', None),
                    "status": "error",
                    "error": str(e)
                })

        # Remove Low-scored queue items for these patent_ids
        low_scores = (
            db.query(Score).filter(Score.patent_id.in_(patent_ids), Score.relevance == "Low").all()
        )
        removed = 0
        for score in low_scores:
            qi = (
                db.query(QueueItem)
                .filter(
                    QueueItem.patent_id == score.patent_id,
                    QueueItem.abstract_sha1 == score.abstract_sha1,
                )
                .first()
            )
            if qi:
                db.delete(qi)
                removed += 1
        db.commit()

        return {
            "ok": True,
            "message": f"Airtable sync complete: {synced} synced, {skipped} skipped, {errors} errors; removed {removed} Low-scored from queue",
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
            "removed": removed,
            "details": details,
        }
    except Exception as e:
        logger.error(f"Airtable sync failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Airtable sync failed: {e}")
    finally:
        db.close()
 