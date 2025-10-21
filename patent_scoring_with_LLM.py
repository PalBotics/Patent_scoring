"""
Patent Scoring System for Autonomous Demining Robot Project

This script automatically evaluates patents from an Airtable database using OpenAI's GPT model
to determine their relevance to an autonomous demining robot project. It maintains a local
SQLite cache to prevent re-processing and updates the Airtable database with results.

Key Features:
- Fetches unscored patents from Airtable
- Evaluates relevance using OpenAI's GPT model
- Caches results in SQLite database
- Updates Airtable with scores
- Deletes low-relevance patents
- Includes retry logic and rate limiting
- Comprehensive logging

Environment Variables (.env):
    AIRTABLE_API_KEY: Your Airtable API key
    AIRTABLE_BASE_ID: Your Airtable base ID
    AIRTABLE_TABLE_NAME: Name of the patents table
    OPENAI_API_KEY: Your OpenAI API key
    PROMPT_VERSION: Version of the scoring prompt (default: v1.0)

Author: Paul Lydick
Last Updated: October 19, 2025
"""

import os
import json
import sqlite3
import hashlib
import logging
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import requests
import openai
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('patent_scoring.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure API keys and settings
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PROMPT_VERSION = os.getenv('PROMPT_VERSION', 'v1.0')

# Validate environment variables
required_vars = [
    'AIRTABLE_API_KEY',
    'AIRTABLE_BASE_ID',
    'AIRTABLE_TABLE_NAME',
    'OPENAI_API_KEY'
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

def init_db() -> sqlite3.Connection:
    """Initialize SQLite database with required schema.
    
    Creates a new SQLite database file if it doesn't exist, or connects to an existing one.
    Sets up the 'scores' table with the following schema:
        - patent_id: Primary key, unique identifier for the patent
        - abstract_sha1: Hash of patent content for detecting changes
        - relevance: 'High', 'Medium', or 'Low'
        - subsystem: JSON array of relevant subsystems
        - title: Patent title
        - abstract: Patent abstract
        - scored_at: Timestamp of scoring
        - prompt_version: Version of prompt used for scoring
    
    Returns:
        sqlite3.Connection: Active database connection
    
    Raises:
        sqlite3.Error: If database creation or schema setup fails
    """
    conn = sqlite3.connect('patent_scores.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scores (
        patent_id TEXT PRIMARY KEY,
        abstract_sha1 TEXT,
        relevance TEXT,
        subsystem TEXT,
        title TEXT,
        abstract TEXT,
        scored_at TEXT DEFAULT CURRENT_TIMESTAMP,
        prompt_version TEXT
    )
    ''')
    
    conn.commit()
    return conn

def compute_sha1(patent_id: str, abstract: str) -> str:
    """Compute SHA1 hash of patent ID, normalized abstract, and prompt version.
    
    Creates a unique identifier for a patent's content that changes if the abstract
    or prompt version changes. This allows detecting when a patent needs re-scoring.
    
    Args:
        patent_id (str): The unique identifier of the patent
        abstract (str): The patent's abstract text
    
    Returns:
        str: SHA1 hash in hexadecimal format
    
    Note:
        The abstract is normalized by:
        1. Converting to lowercase
        2. Normalizing whitespace to single spaces
        3. Combining with patent_id and PROMPT_VERSION
    """
    normalized_abstract = ' '.join(abstract.lower().split())
    content = f"{patent_id}|{normalized_abstract}|{PROMPT_VERSION}"
    return hashlib.sha1(content.encode('utf-8')).hexdigest()

def check_if_scored(conn: sqlite3.Connection, patent_id: str, abstract_sha1: str) -> Optional[Tuple[str, List[str]]]:
    """Check if a patent has already been scored in the local cache.
    
    Queries the SQLite database for an existing score. A match requires both:
    1. Matching patent_id
    2. Matching abstract_sha1 (ensures content hasn't changed)
    
    Args:
        conn (sqlite3.Connection): Active database connection
        patent_id (str): The patent's unique identifier
        abstract_sha1 (str): SHA1 hash of the patent's content
    
    Returns:
        Optional[Tuple[str, List[str]]]: If found, returns (relevance, subsystems)
            where relevance is 'High', 'Medium', or 'Low' and subsystems is a list
            of relevant subsystem names. Returns None if no match found.
    
    Note:
        The subsystem field is stored as a JSON string in SQLite and converted
        back to a list when retrieved.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT relevance, subsystem FROM scores WHERE patent_id = ? AND abstract_sha1 = ?",
        (patent_id, abstract_sha1)
    )
    result = cursor.fetchone()
    
    if result:
        relevance, subsystem_str = result
        subsystem = json.loads(subsystem_str) if subsystem_str else []
        return relevance, subsystem
    return None

def store_result(
    conn: sqlite3.Connection,
    patent_id: str,
    abstract_sha1: str,
    relevance: str,
    subsystem: List[str],
    title: str,
    abstract: str,
    prompt_version: str
) -> None:
    """Store patent scoring result in SQLite database."""
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO scores
    (patent_id, abstract_sha1, relevance, subsystem, title, abstract, prompt_version)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        patent_id,
        abstract_sha1,
        relevance,
        json.dumps(subsystem),
        title,
        abstract,
        prompt_version
    ))
    conn.commit()

def fetch_unscored_patents(batch_size: int = 100, offset: Optional[str] = None) -> List[Dict]:
    """Fetch unscored patents from Airtable database.
    
    Queries Airtable API for patents that:
    1. Have no relevance score yet (Relevance field is empty)
    2. Have non-empty abstracts
    
    Args:
        batch_size (int, optional): Number of records to process per batch.
            Defaults to 100.
        offset (Optional[str], optional): Airtable pagination token. 
            Defaults to None.
    
    Returns:
        List[Dict]: List of patent records, each containing:
            - id: Airtable record ID
            - patent_id: Patent's unique identifier
            - title: Patent title
            - abstract: Patent abstract
            - pub_date: Publication date (optional)
    
    Raises:
        requests.exceptions.RequestException: For API communication errors
        ValueError: If required environment variables are missing
    """
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    params = {
        "filterByFormula": "AND({Relevance} = '', {Abstract} != '')",
        "fields": ["Patent ID", "Title", "Abstract", "Publication Date"],
        "maxRecords": batch_size,  # Only get the requested batch size
        "sort": [{"field": "Patent ID", "direction": "asc"}]  # Ensure consistent ordering
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        records = data.get('records', [])
        
        batch_records = [{
            'id': record['id'],
            'patent_id': record['fields'].get('Patent ID', ''),
            'title': record['fields'].get('Title', ''),
            'abstract': record['fields'].get('Abstract', ''),
            'pub_date': record['fields'].get('Publication Date', '')
        } for record in records]
        
        logger.info(f"Fetched batch of {len(batch_records)} patents")
        return batch_records
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching patents from Airtable: {e}")
        raise
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching patents from Airtable: {e}")
        raise

def load_state() -> Dict:
    """Load processing state from state file.
    
    Returns:
        Dict: Current processing state with keys:
            - last_offset: Last Airtable offset processed
            - total_processed: Total number of patents processed
            - last_patent_id: ID of last successfully processed patent
    """
    state_file = Path("patent_processing_state.json")
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"last_offset": None, "total_processed": 0, "last_patent_id": None}

def save_state(state: Dict) -> None:
    """Save current processing state to file.
    
    Args:
        state (Dict): Current processing state
    """
    with open("patent_processing_state.json", "w") as f:
        json.dump(state, f)

class APIRateLimitError(Exception):
    """Exception raised when hitting API rate limits.
    
    Custom exception to handle rate limiting scenarios from external APIs
    (OpenAI and Airtable). Used to trigger retry logic with exponential
    backoff.
    
    Attributes:
        message (str): Explanation of the rate limit error
        retry_after (int, optional): Suggested wait time before retry
    """
    pass

def get_relevance_score(title: str, abstract: str, max_retries: int = 3) -> Dict:
    """Evaluate patent relevance using OpenAI's GPT model with retry logic.
    
    Sends the patent title and abstract to OpenAI's API for evaluation of its
    relevance to the autonomous demining robot project.
    
    Args:
        title (str): The patent's title
        abstract (str): The patent's abstract
        max_retries (int, optional): Maximum number of retry attempts for API calls.
            Defaults to 3.
    
    Returns:
        Dict: Evaluation result with format:
            {
                "Relevance": "High" | "Medium" | "Low",
                "Subsystem": ["Detection", "AI/Fusion", "Swarm", "Remediation"]
            }
    
    Raises:
        APIRateLimitError: If API rate limits are hit after all retries
        ValueError: If OpenAI's response doesn't match expected format
        Exception: For other API or processing errors
    
    Note:
        - Uses exponential backoff between retries
        - For "Low" relevance, Subsystem list is always empty
        - Response is validated for correct format before returning
    """
    system_message = """You evaluate patents for an autonomous demining robot project.
Return JSON:
{
    "Relevance": "High" | "Medium" | "Low",
    "Subsystem": ["Detection", "AI/Fusion", "Swarm", "Remediation"]
}
Rules:
- If Relevance = Low, Subsystem = [].
- If Relevance = Medium or High, include all relevant subsystems."""

    user_message = f"Title: {title}\nAbstract: {abstract}"

    for attempt in range(max_retries):
        try:
            response = openai.chat.completions.create(
                model="gpt-4-turbo",  # Adjust model as needed
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )
            # OpenAI v1.x returns response.choices[0].message.content
            result = json.loads(response.choices[0].message.content)
            # Validate response format
            if not isinstance(result, dict) or \
               'Relevance' not in result or \
               'Subsystem' not in result or \
               result['Relevance'] not in ['High', 'Medium', 'Low'] or \
               not isinstance(result['Subsystem'], list):
                raise ValueError("Invalid response format from OpenAI")
            # Ensure Low relevance has empty subsystem list
            if result["Relevance"] == "Low":
                result["Subsystem"] = []
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise APIRateLimitError(f"OpenAI API error after {max_retries} retries: {str(e)}")
            logger.error(f"Error getting relevance score (attempt {attempt+1}): {e}")
            time.sleep(2 ** attempt)  # Exponential backoff

def update_airtable(record_id: str, relevance: str, subsystem: List[str]) -> None:
    """Update patent record in Airtable with relevance score and subsystems.
    
    Updates a patent record in Airtable with its evaluation results using
    the PATCH API endpoint.
    
    Args:
        record_id (str): Airtable record ID to update
        relevance (str): Relevance score ('High', 'Medium', 'Low')
        subsystem (List[str]): List of relevant subsystems
    
    Raises:
        requests.exceptions.RequestException: For API communication errors
    
    Note:
        - Subsystems are joined into a comma-separated string for Airtable
        - Empty subsystem list results in empty string in Airtable
        - Uses AIRTABLE_* environment variables for authentication
    """
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "fields": {
            "Relevance": relevance,
            "Subsystem": subsystem if subsystem else []  # Send as array for Multiple Select field
        }
    }
    
    try:
        response = requests.patch(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating Airtable record: {e}")
        raise

def delete_airtable_record(record_id: str) -> None:
    """Delete a patent record from Airtable.
    
    Removes a record from Airtable, typically used for patents scored as
    'Low' relevance to keep the database clean.
    
    Args:
        record_id (str): Airtable record ID to delete
    
    Raises:
        requests.exceptions.RequestException: For API communication errors
    
    Note:
        - This operation is permanent and cannot be undone
        - The record remains in local SQLite cache for reference
        - Uses AIRTABLE_* environment variables for authentication
    """
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}"
    }
    
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error deleting Airtable record: {e}")
        raise

def parse_args():
    """Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Patent scoring system for demining robot project")
    parser.add_argument("--batch-size", type=int, default=100,
                      help="Number of patents to process per batch (default: 100, Airtable's maximum)")
    parser.add_argument("--reset-state", action="store_true",
                      help="Reset the processing state and start from beginning")
    return parser.parse_args()

def main():
    """Main workflow for patent scoring process.
    
    Orchestrates the entire patent scoring workflow:
    1. Initializes SQLite database
    2. Fetches unscored patents from Airtable in batches
    3. For each patent:
        a. Checks local cache for existing score
        b. If not found, gets new score from OpenAI
        c. Stores result in SQLite
        d. Updates or deletes record in Airtable
    
    The process includes:
    - Batch processing with configurable size
    - State tracking for resume capability
    - Rate limiting (1 second between API calls)
    - Error handling with logging
    - Progress tracking
    - Resource cleanup
    
    Command line arguments:
        --batch-size: Number of patents to process per batch (default: 25)
        --reset-state: Reset the processing state and start from beginning
    
    Raises:
        ValueError: If required environment variables are missing
        Exception: For other unrecoverable errors
    
    Note:
        - Run this script via Task Scheduler for automation
        - Check patent_scoring.log for detailed execution logs
        - Configure environment variables in .env file
        - State is saved in patent_processing_state.json
    """
    try:
        args = parse_args()
        if args.reset_state:
            logger.info("Resetting processing state")
            save_state({"last_offset": None, "total_processed": 0, "last_patent_id": None})
        
        state = load_state()
        logger.info(f"Resuming from state: {state}")
        
        conn = init_db()
        logger.info("Database initialized")
        
        while True:
            patents = fetch_unscored_patents(
                batch_size=args.batch_size,
                offset=state["last_offset"]
            )
            
            if not patents:
                logger.info("No more patents to process")
                break
                
            logger.info(f"Processing batch of {len(patents)} patents")
            
            for i, p in enumerate(patents, 1):
                patent_id = p["patent_id"]
                abstract = p["abstract"]
                sha1 = compute_sha1(patent_id, abstract)
                
                logger.info(f"Processing patent {state['total_processed'] + i}: {patent_id}")
                
                try:
                    cached = check_if_scored(conn, patent_id, sha1)
                    if cached:
                        relevance, subsystem = cached
                        logger.info(f"Using cached score for {patent_id}")
                    else:
                        logger.info(f"Evaluating patent {patent_id}")
                        result = get_relevance_score(p["title"], abstract)
                        relevance = result["Relevance"]
                        subsystem = result["Subsystem"]
                        store_result(
                            conn,
                            patent_id,
                            sha1,
                            relevance,
                            subsystem,
                            p["title"],
                            abstract,
                            PROMPT_VERSION
                        )
                    
                    if relevance == "Low":
                        logger.info(f"Deleting low relevance patent {patent_id}")
                        delete_airtable_record(p["id"])
                    else:
                        logger.info(f"Updating patent {patent_id} with relevance: {relevance}")
                        update_airtable(p["id"], relevance, subsystem)
                    
                    # Update state after successful processing
                    state["last_patent_id"] = patent_id
                    state["total_processed"] += 1
                    save_state(state)
                    
                    # Small delay to respect API rate limits
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing patent {patent_id}: {e}")
                    # Continue with next patent on error
                    continue
            
            # We don't need to manually update the offset as we'll get all records in one call
            logger.info(f"Completed batch. Total processed: {state['total_processed']}")
            
            # Since we're getting all records in one call now, we can break
            break
    
    except Exception as e:
        logger.error(f"Error in main workflow: {e}")
        raise
    
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()