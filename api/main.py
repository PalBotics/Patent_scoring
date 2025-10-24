import os
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from typing import Optional, List
import sys
from pathlib import Path
# Add parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent))

from api.schemas import (
    RecordSummary, RecordDetail, ListRecordsResponse,
    ScoreRequest, ScoreResponse, ErrorResponse, Provenance,
    SettingsResponse, ScoresListResponse, ScoreListItem
)
from datetime import datetime
import db
import scorer
from api import airtable_service
from api.db import get_db, init_db as init_database
from sqlalchemy.orm import Session

load_dotenv()

# Initialize database on startup
init_database()

API_KEY = os.getenv("APP_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v1.0")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Patents")

app = FastAPI(title="Patent Scoring API", version="0.1.0")

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_api_key(authorization: Optional[str] = Header(None)):
    try:
        if not API_KEY:
            raise HTTPException(status_code=500, detail="Server misconfigured: APP_API_KEY not set.")
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization header")
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid Authorization header format")
        token = authorization.split(" ", 1)[1]
        if token != API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return token
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error in get_api_key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/records", response_model=ListRecordsResponse)
async def list_records(limit: int = 25, offset: int = 0, q: Optional[str] = None, relevance: Optional[str] = None, subsystem: Optional[str] = None, api_key: str = Depends(get_api_key)):
    try:
        # Fetch records from Airtable
        records, total = airtable_service.fetch_records(limit=limit, offset=offset)
        
        # Convert Airtable records to RecordSummary format
        record_list = []
        for i, rec in enumerate(records):
            if i < offset:
                continue
            if i >= offset + limit:
                break
            # Normalize fields from Airtable to avoid validation errors
            raw_subsystem = rec.get('subsystem', [])
            if raw_subsystem is None:
                subsys: List[str] = []
            elif isinstance(raw_subsystem, str):
                subsys = [raw_subsystem]
            elif isinstance(raw_subsystem, list):
                subsys = [str(x) for x in raw_subsystem if x is not None]
            else:
                subsys = []

            pub_date_val = rec.get('pub_date', '')
            pub_date_str = str(pub_date_val) if pub_date_val is not None else ''
            record_list.append(RecordSummary(
                id=rec.get('id', ''),
                patent_id=rec.get('patent_id', ''),
                title=rec.get('title', ''),
                abstract=rec.get('abstract', ''),
                relevance=rec.get('relevance'),
                score=0,  # Default score
                subsystem=subsys,
                sha1='',  # Not stored in Airtable
                updated_at=pub_date_str
            ))
        
        return ListRecordsResponse(total=total, offset=offset, limit=limit, records=record_list)
    except Exception as e:
        import traceback
        print("Error in list_records:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Airtable error: {str(e)}")

@app.get("/api/v1/records/{record_id}", response_model=RecordDetail)
def get_record(record_id: str, api_key: str = Depends(get_api_key)):
    conn = db.init_db()
    cur = conn.cursor()
    cur.execute("SELECT id, patent_id, title, abstract, relevance, score, subsystem, sha1, updated_at, provenance FROM patent_scores WHERE id = ?", (record_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found.")
    prov = None
    if row[9]:
        try:
            prov = Provenance.parse_raw(row[9])
        except Exception:
            prov = None
    return RecordDetail(
        id=row[0],
        patent_id=row[1],
        title=row[2],
        abstract=row[3],
        relevance=row[4],
        score=row[5],
        subsystem=(eval(row[6]) if row[6] else []),
        sha1=row[7],
        updated_at=row[8],
        provenance=prov
    )

@app.post("/api/v1/score", response_model=ScoreResponse)
async def score_record(req: ScoreRequest, api_key: str = Depends(get_api_key)):
    try:
        # Use scorer.keyword_score or LLM depending on req.mode
        if req.mode == "keyword":
            result = scorer.keyword_score(title=req.title, abstract=req.abstract, mapping=req.mapping or {})
            prov = Provenance(method="keyword", prompt_version=None, scored_at=datetime.utcnow())
        else:
            # For now, just call keyword_score as a placeholder
            result = scorer.keyword_score(title=req.title, abstract=req.abstract, mapping=req.mapping or {})
            prov = Provenance(method="llm", prompt_version=os.getenv("PROMPT_VERSION"), scored_at=datetime.utcnow())
        
        # Ensure result has all required fields with proper types
        return ScoreResponse(
            relevance=str(result.get("relevance", "Low")),
            score=int(result.get("score", 0)),
            subsystem=list(result.get("subsystem", [])),
            sha1=str(result.get("sha1", "")),
            provenance=prov
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
    """
    Get current system settings (read-only).
    No auth required for settings visibility.
    """
    return SettingsResponse(
        openaiModel=OPENAI_MODEL,
        promptVersion=PROMPT_VERSION,
        airtableBaseId=AIRTABLE_BASE_ID if AIRTABLE_BASE_ID else "not-set",
        airtableTableName=AIRTABLE_TABLE_NAME,
        adminApiKeySet=bool(API_KEY)
    )


@app.get("/api/scores", response_model=ScoresListResponse)
async def list_scores(
    page: int = 1,
    page_size: int = 50,
    relevance: Optional[str] = None,
    search: Optional[str] = None,
    source: Optional[str] = None,
    db: Session = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """
    List scored patents with filtering and pagination.
    """
    from api.models import Score
    from sqlalchemy import or_, and_

    query = db.query(Score)

    # Apply filters
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
                Score.patent_id.ilike(search_term)
            )
        )

    # Get total count
    total = query.count()

    # Paginate
    offset = (page - 1) * page_size
    items_db = query.order_by(Score.scored_at.desc()).offset(offset).limit(page_size).all()

    # Convert to response format
    items = [
        ScoreListItem(
            patentId=item.patent_id,
            abstractSha1=item.abstract_sha1,
            relevance=item.relevance or "Low",
            subsystem=eval(item.subsystem_json) if item.subsystem_json else [],
            title=item.title,
            abstract=item.abstract,
            pubDate=item.pub_date,
            source=item.source,
            scoredAt=item.scored_at.isoformat() if item.scored_at else ""
        )
        for item in items_db
    ]

    return ScoresListResponse(
        items=items,
        page=page,
        pageSize=page_size,
        total=total
    )
