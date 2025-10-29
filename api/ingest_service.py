"""
Ingest service for USPTO patent files.
Parses CSV/XML files, deduplicates against master DB, scores new patents.
"""
import hashlib
import csv
import json
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
from xml.etree.ElementTree import iterparse
import gzip
import zipfile
import io

from sqlalchemy.orm import Session
from api.models import Score, QueueItem, IngestJob
from api.db import SessionLocal

logger = logging.getLogger(__name__)


def compute_sha1(text: str) -> str:
    """Compute SHA1 hash of text."""
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def _strip_ns(tag: str) -> str:
    """Remove XML namespace from tag."""
    return tag.split('}', 1)[-1] if '}' in tag else tag


def _text(elem) -> str:
    """Extract text content from XML element."""
    return (elem.text or '').strip() if elem is not None else ''


def _iter_children(elem, name: str):
    """Iterate over child elements with matching tag name."""
    for child in elem:
        if _strip_ns(child.tag) == name:
            yield child


def extract_record_from_xml(doc_elem) -> Optional[Dict]:
    """
    Extract patent record from XML element.
    Returns dict with: patent_id, title, abstract, pub_date, source
    """
    try:
        doc_tag = _strip_ns(doc_elem.tag)
        is_grant = 'grant' in doc_tag.lower()
        source = "GRANT" if is_grant else "IPAB"

        # Extract document number
        pub_ref = doc_elem.find('.//{*}publication-reference/{*}document-id')
        if pub_ref is None:
            return None
        
        doc_num = _text(pub_ref.find('{*}doc-number'))
        kind = _text(pub_ref.find('{*}kind'))
        date = _text(pub_ref.find('{*}date'))
        country = _text(pub_ref.find('{*}country'))
        
        patent_id = f"{country}{doc_num}{kind}" if country and doc_num and kind else doc_num
        
        # Extract title
        title_elem = doc_elem.find('.//{*}invention-title')
        title = _text(title_elem) if title_elem is not None else ''
        
        # Extract abstract
        abstract_parts = []
        abstract_elem = doc_elem.find('.//{*}abstract')
        if abstract_elem is not None:
            for p in _iter_children(abstract_elem, 'p'):
                abstract_parts.append(_text(p))
        abstract = ' '.join(abstract_parts)
        
        if not patent_id or not abstract:
            return None
        
        return {
            'patent_id': patent_id,
            'title': title,
            'abstract': abstract,
            'pub_date': date,
            'source': source
        }
    except Exception as e:
        logger.warning(f"Failed to extract record: {e}")
        return None


def parse_xml_stream(stream) -> List[Dict]:
    """
    Parse USPTO XML stream and extract patent records.
    Returns list of dicts with patent_id, title, abstract, pub_date, source.
    """
    records = []
    try:
        context = iterparse(stream, events=('start', 'end'))
        _, root = next(context)
        
        for event, elem in context:
            if event == 'end':
                tag = _strip_ns(elem.tag)
                if tag in ('us-patent-application', 'us-patent-grant'):
                    rec = extract_record_from_xml(elem)
                    if rec:
                        records.append(rec)
                    elem.clear()
                    root.clear()
    except Exception as e:
        logger.error(f"XML parsing error: {e}")
    
    return records


def parse_csv_stream(stream) -> List[Dict]:
    """
    Parse CSV stream and extract patent records.
    Handles multiple CSV formats including USPTO export format.
    Expected columns: patent_id/Document ID, title/Title, abstract (various), pub_date/Date Published
    """
    records = []
    try:
        # Read as text stream with UTF-8-sig to handle BOM
        text_stream = io.TextIOWrapper(stream, encoding='utf-8-sig')
        reader = csv.DictReader(text_stream)
        
        for row in reader:
            # Normalize column names (handle snake_case and camelCase)
            normalized = {}
            for k, v in row.items():
                if k:  # Skip empty column names
                    # Strip BOM and normalize
                    key = k.strip().lstrip('\ufeff').lower().replace(' ', '_').replace('/', '_').replace('-', '_')
                    normalized[key] = (v or '').strip()
            
            # Try multiple column name variations
            patent_id = (
                normalized.get('patent_id') or 
                normalized.get('patentid') or 
                normalized.get('document_id') or
                normalized.get('doc_number') or
                normalized.get('publication_number')
            )
            
            title = (
                normalized.get('title') or
                normalized.get('invention_title') or
                ''
            )
            
            # Abstract might be in Title field if there's no separate abstract column
            # Or in Notes field for USPTO exports
            abstract = (
                normalized.get('abstract') or
                normalized.get('notes') or
                normalized.get('summary') or
                title  # Fallback to title if no abstract
            )
            
            pub_date = (
                normalized.get('pub_date') or 
                normalized.get('pubdate') or 
                normalized.get('date_published') or
                normalized.get('date') or
                normalized.get('filing_date') or
                ''
            )
            
            source = normalized.get('source', 'USPTO CSV')
            
            # Skip if we don't have minimum required fields
            if not patent_id:
                continue
                
            # Use title as abstract if abstract is missing or too short
            if not abstract or len(abstract) < 10:
                if len(title) >= 10:
                    abstract = title
                else:
                    continue  # Skip records with no meaningful content
            
            if patent_id and abstract:
                records.append({
                    'patent_id': patent_id,
                    'title': title,
                    'abstract': abstract,
                    'pub_date': pub_date,
                    'source': source
                })
    except Exception as e:
        logger.error(f"CSV parsing error: {e}")
    
    return records


def parse_file(file_path: str) -> List[Dict]:
    """
    Parse USPTO file (CSV, XML, XML.GZ, or ZIP containing XMLs).
    Returns list of patent records.
    """
    path = Path(file_path)
    records = []
    
    try:
        if path.suffix.lower() == '.csv':
            with open(path, 'rb') as f:
                records = parse_csv_stream(f)
        
        elif path.suffix.lower() == '.gz':
            with gzip.open(path, 'rb') as f:
                records = parse_xml_stream(f)
        
        elif path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path, 'r') as zf:
                for name in zf.namelist():
                    if name.lower().endswith('.xml'):
                        with zf.open(name) as f:
                            records.extend(parse_xml_stream(f))
        
        elif path.suffix.lower() == '.xml':
            with open(path, 'rb') as f:
                records = parse_xml_stream(f)
        
        else:
            logger.error(f"Unsupported file type: {path.suffix}")
    
    except Exception as e:
        logger.error(f"File parsing error: {e}")
    
    return records


def check_existing_score(db: Session, patent_id: str, abstract_sha1: str) -> Optional[Score]:
    """
    Check if patent has already been scored in master DB.
    Returns Score object if found, None otherwise.
    """
    return db.query(Score).filter(
        Score.patent_id == patent_id,
        Score.abstract_sha1 == abstract_sha1
    ).first()


def check_existing_in_queue(db: Session, patent_id: str, abstract_sha1: str) -> Optional[QueueItem]:
    """
    Check if patent is already in the queue.
    Returns QueueItem object if found, None otherwise.
    """
    return db.query(QueueItem).filter(
        QueueItem.patent_id == patent_id,
        QueueItem.abstract_sha1 == abstract_sha1
    ).first()


def process_ingest_job(job_id: int, file_path: str) -> Dict:
    """
    Process ingest job: parse file, deduplicate, prepare for scoring.
    
    Returns:
        {
            'total_parsed': int,
            'existing_scores': int,
            'new_to_score': int,
            'error': Optional[str]
        }
    """
    db = SessionLocal()
    try:
        # Update job status
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if not job:
            return {'error': 'Job not found'}
        
        job.status = 'running'
        db.commit()
        
        # Parse file
        logger.info(f"Parsing file: {file_path}")
        records = parse_file(file_path)
        
        if not records:
            job.status = 'failed'
            job.log = 'No records found in file'
            db.commit()
            return {
                'total_parsed': 0,
                'existing_scores': 0,
                'new_to_score': 0,
                'error': 'No records found'
            }
        
        logger.info(f"Parsed {len(records)} records")
        
        # Deduplicate against master DB and queue
        existing_count = 0
        queued_count = 0
        new_count = 0
        
        for rec in records:
            abstract_sha1 = compute_sha1(rec['abstract'])
            
            # Check if already scored
            existing = check_existing_score(db, rec['patent_id'], abstract_sha1)
            
            if existing:
                existing_count += 1
                logger.debug(f"Skipping {rec['patent_id']} - already scored")
                continue
            
            # Check if already in queue
            in_queue = check_existing_in_queue(db, rec['patent_id'], abstract_sha1)
            
            if in_queue:
                queued_count += 1
                logger.debug(f"Skipping {rec['patent_id']} - already in queue")
                continue
            
            # Add to queue for scoring (it's new)
            queue_item = QueueItem(
                patent_id=rec['patent_id'],
                abstract_sha1=abstract_sha1,
                title=rec.get('title', ''),
                abstract=rec['abstract'],
                pub_date=rec.get('pub_date', ''),
                source=rec.get('source', 'UNKNOWN'),
                status='pending'
            )
            db.add(queue_item)
            new_count += 1
        
        db.commit()
        
        # Update job
        job.status = 'completed'
        job.matched_count = existing_count
        job.enqueued_count = new_count
        job.completed_at = datetime.now()
        job.log = f"Parsed {len(records)}: {existing_count} already scored, {queued_count} already queued, {new_count} newly enqueued"
        db.commit()
        
        logger.info(f"Ingest complete: {new_count} new, {existing_count} existing")
        
        return {
            'total_parsed': len(records),
            'existing_scores': existing_count,
            'new_to_score': new_count,
            'error': None
        }
    
    except Exception as e:
        logger.error(f"Ingest job {job_id} failed: {e}", exc_info=True)
        job = db.query(IngestJob).filter(IngestJob.id == job_id).first()
        if job:
            job.status = 'failed'
            job.log = str(e)[:500]
            db.commit()
        return {
            'total_parsed': 0,
            'existing_scores': 0,
            'new_to_score': 0,
            'error': str(e)
        }
    finally:
        db.close()
