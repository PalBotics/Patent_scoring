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

from api.schemas import RecordSummary, RecordDetail, ListRecordsResponse, ScoreRequest, ScoreResponse, ErrorResponse, Provenance
from datetime import datetime
import db
import scorer

load_dotenv()

API_KEY = os.getenv("APP_API_KEY")

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
        # Use test database if it exists
        db_path = "test_patent_scores.db" if os.path.exists("test_patent_scores.db") else "patent_scores.db"
        conn = sqlite3.connect(db_path)
        
        # For MVP, ignore filters except limit/offset
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patent_scores")
        total = cur.fetchone()[0] or 0
        
        # If no records exist yet, return empty list
        if total == 0:
            return ListRecordsResponse(total=0, offset=offset, limit=limit, records=[])
            
        cur.execute("SELECT id, patent_id, title, abstract, relevance, score, subsystem, sha1, updated_at FROM patent_scores ORDER BY updated_at DESC LIMIT ? OFFSET ?", (limit, offset))
        rows = cur.fetchall()
        records = []
        for row in rows:
            records.append(RecordSummary(
                id=str(row[0]) if row[0] else "",  # Ensure ID is string
                patent_id=str(row[1]) if row[1] else "",
                title=str(row[2]) if row[2] else "",
                abstract=str(row[3]) if row[3] else "",
                relevance=str(row[4]) if row[4] else None,
                score=int(row[5]) if row[5] is not None else None,
                subsystem=eval(row[6]) if row[6] else [],
                sha1=str(row[7]) if row[7] else "",
                updated_at=row[8]
            ))
        return ListRecordsResponse(total=total, offset=offset, limit=limit, records=records)
    except Exception as e:
        print(f"Error in list_records: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
