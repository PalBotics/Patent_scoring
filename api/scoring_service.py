"""
Batch scoring service for patent queue.
Processes pending patents, scores them, filters by relevance, and stores results.
"""
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from api.models import Score, QueueItem
from api.db import SessionLocal
import scorer

logger = logging.getLogger(__name__)


def score_patent(
    title: str,
    abstract: str,
    mapping: Optional[Dict[str, List[str]]] = None,
    mode: str = "keyword"
) -> Dict:
    """
    Score a single patent using keyword or LLM method.
    
    Args:
        title: Patent title
        abstract: Patent abstract
        mapping: Subsystem keyword mapping (for keyword mode)
        mode: "keyword" or "llm"
    
    Returns:
        {
            'relevance': str,  # "High" | "Medium" | "Low"
            'subsystem': List[str]
        }
    """
    if mode == "llm":
        # TODO: Implement LLM scoring
        logger.warning("LLM scoring not yet implemented, falling back to keyword")
        mode = "keyword"
    
    if mode == "keyword":
        # Use existing keyword scorer
        if mapping is None:
            # Default mapping - load from file or use hardcoded defaults
            mapping = get_default_mapping()
        
        result = scorer.keyword_score(title=title, abstract=abstract, mapping=mapping)
        return {
            'relevance': result.get('Relevance', 'Low'),
            'subsystem': result.get('Subsystem', [])
        }
    
    return {'relevance': 'Low', 'subsystem': []}


def get_default_mapping() -> Dict[str, List[str]]:
    """
    Get default subsystem keyword mapping.
    TODO: Load from config file or database.
    """
    return {
        "Mobility": ["mobility", "wheel", "track", "locomotion", "navigation", "autonomous", "terrain"],
        "Sensing": ["sensor", "camera", "lidar", "radar", "detection", "imaging", "sonar"],
        "Manipulation": ["manipulator", "arm", "gripper", "actuator", "end effector", "grasping"],
        "Control": ["control", "controller", "algorithm", "processing", "computing", "software"],
        "Power": ["power", "battery", "energy", "charging", "fuel", "generator"],
        "Communication": ["communication", "wireless", "telemetry", "data transmission", "network"],
        "Demining": ["mine", "explosive", "demining", "clearance", "ordnance", "UXO", "IED"]
    }


def process_queue_batch(
    batch_size: int = 10,
    mode: str = "keyword",
    mapping: Optional[Dict[str, List[str]]] = None,
    min_relevance: str = "Medium"
) -> Dict:
    """
    Process a batch of pending patents from queue.
    Scores them, filters by relevance, and stores in scores table.
    
    Args:
        batch_size: Number of patents to process in this batch
        mode: "keyword" or "llm"
        mapping: Subsystem keyword mapping (for keyword mode)
        min_relevance: Minimum relevance to store ("High", "Medium", "Low")
    
    Returns:
        {
            'processed': int,
            'scored': int,
            'filtered': int,
            'errors': int
        }
    """
    db = SessionLocal()
    try:
        # Get pending items from queue
        pending = db.query(QueueItem).filter(
            QueueItem.status == 'pending'
        ).limit(batch_size).all()
        
        if not pending:
            logger.info("No pending items in queue")
            return {
                'processed': 0,
                'scored': 0,
                'filtered': 0,
                'errors': 0
            }
        
        processed = 0
        scored = 0
        filtered = 0
        errors = 0
        
        relevance_order = {"High": 3, "Medium": 2, "Low": 1}
        min_score = relevance_order.get(min_relevance, 2)
        
        for item in pending:
            try:
                # Score the patent
                result = score_patent(
                    title=item.title or '',
                    abstract=item.abstract or '',
                    mapping=mapping,
                    mode=mode
                )
                
                relevance = result['relevance']
                subsystem = result['subsystem']
                processed += 1
                
                # Filter by minimum relevance
                if relevance_order.get(relevance, 0) >= min_score:
                    # Store in scores table
                    score_entry = Score(
                        patent_id=item.patent_id,
                        abstract_sha1=item.abstract_sha1,
                        relevance=relevance,
                        subsystem_json=json.dumps(subsystem),
                        title=item.title,
                        abstract=item.abstract,
                        pub_date=item.pub_date,
                        source=item.source,
                        model_id=f"{mode}-scorer",
                        prompt_version="v1.0",
                        scored_at=datetime.now()
                    )
                    db.merge(score_entry)
                    scored += 1
                    
                    # Update queue item status
                    item.status = 'scored'
                    logger.info(f"Scored {item.patent_id}: {relevance} ({', '.join(subsystem)})")
                else:
                    # Low score - still mark as scored, will be removed during Airtable sync
                    item.status = 'scored'
                    filtered += 1
                    logger.info(f"Scored (Low) {item.patent_id}: {relevance}")
                
            except Exception as e:
                logger.error(f"Error scoring {item.patent_id}: {e}", exc_info=True)
                item.status = 'error'
                errors += 1
        
        db.commit()
        
        logger.info(f"Batch complete: {processed} processed, {scored} scored, {filtered} filtered, {errors} errors")
        
        return {
            'processed': processed,
            'scored': scored,
            'filtered': filtered,
            'errors': errors
        }
    
    except Exception as e:
        logger.error(f"Batch processing error: {e}", exc_info=True)
        db.rollback()
        return {
            'processed': 0,
            'scored': 0,
            'filtered': 0,
            'errors': 1
        }
    finally:
        db.close()


def process_all_pending(
    mode: str = "keyword",
    mapping: Optional[Dict[str, List[str]]] = None,
    min_relevance: str = "Medium",
    batch_size: int = 10
) -> Dict:
    """
    Process all pending patents in queue.
    Continues processing batches until queue is empty.
    
    Returns summary statistics.
    """
    total_stats = {
        'processed': 0,
        'scored': 0,
        'filtered': 0,
        'errors': 0
    }
    
    while True:
        batch_stats = process_queue_batch(
            batch_size=batch_size,
            mode=mode,
            mapping=mapping,
            min_relevance=min_relevance
        )
        
        if batch_stats['processed'] == 0:
            break
        
        for key in total_stats:
            total_stats[key] += batch_stats[key]
    
    logger.info(f"All pending processed: {total_stats}")
    return total_stats
