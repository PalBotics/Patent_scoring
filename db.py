import sqlite3
import hashlib
import json
from typing import List, Optional, Tuple

PROMPT_VERSION = "v1.0"

def init_db(db_path: str = 'patent_scores.db') -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
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


def compute_sha1(patent_id: str, abstract: str, prompt_version: str = PROMPT_VERSION) -> str:
    normalized_abstract = ' '.join(abstract.lower().split())
    content = f"{patent_id}|{normalized_abstract}|{prompt_version}"
    return hashlib.sha1(content.encode('utf-8')).hexdigest()


def check_if_scored(conn: sqlite3.Connection, patent_id: str, abstract_sha1: str) -> Optional[Tuple[str, List[str]]]:
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


def store_result(conn: sqlite3.Connection, patent_id: str, abstract_sha1: str,
                relevance: str, subsystem: List[str], title: str, abstract: str,
                prompt_version: str) -> None:
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
