import os
from typing import Dict, List, Optional, Tuple, Union

import requests
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME", "Patents")


def _base_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def _normalize_record(record: Dict) -> Dict:
    fields = record.get("fields", {}) or {}
    return {
        "id": record.get("id", ""),
        "patent_id": fields.get("Patent ID", ""),
        "title": fields.get("Title", ""),
        "abstract": fields.get("Abstract", ""),
        "relevance": fields.get("Relevance"),
        "subsystem": fields.get("Subsystem", []) or [],
        "pub_date": fields.get("Publication Date", ""),
    }


def fetch_records(
    limit: int = 25,
    offset: int = 0,
    q: Optional[str] = None,
    relevance: Optional[str] = None,
    subsystem: Optional[str] = None,
) -> Tuple[List[Dict], int]:
    """
    Fetch a window of records from Airtable with a real total count.

    Args:
        limit: number of records to return
        offset: zero-based index into the full record list
        q: search query to filter title/abstract
        relevance: filter by relevance level (High, Medium, Low, etc.)
        subsystem: filter by subsystem

    Returns:
        (records_window, total_count)
    """
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME):
        raise RuntimeError("Airtable environment variables not configured")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = _base_headers()

    # Build filterByFormula
    formula_parts = []
    if q:
        # Search in Title and Abstract fields
        # Using SEARCH which is case-insensitive and returns position or ERROR
        q_escaped = q.replace('"', '\\"')
        formula_parts.append(
            f"OR(SEARCH(LOWER(\"{q_escaped}\"), LOWER({{Title}})), SEARCH(LOWER(\"{q_escaped}\"), LOWER({{Abstract}})))"
        )
    if relevance:
        relevance_escaped = relevance.replace('"', '\\"')
        formula_parts.append(f'{{Relevance}} = "{relevance_escaped}"')
    if subsystem:
        subsystem_escaped = subsystem.replace('"', '\\"')
        formula_parts.append(f'FIND("{subsystem_escaped}", {{Subsystem}})')

    filter_formula = None
    if formula_parts:
        if len(formula_parts) == 1:
            filter_formula = formula_parts[0]
        else:
            filter_formula = "AND(" + ", ".join(formula_parts) + ")"

    buffer: List[Dict] = []
    total_count = 0
    token: Optional[str] = None
    page_size = 100  # Airtable max page size

    while True:
        params: Dict[str, Union[str, int]] = {
            "pageSize": page_size,
            "sort[0][field]": "Patent ID",
            "sort[0][direction]": "asc",
        }
        if filter_formula:
            params["filterByFormula"] = filter_formula
        if token:
            params["offset"] = token

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

        batch = [_normalize_record(r) for r in data.get("records", [])]
        total_count += len(batch)

        # Accumulate only until we have enough to slice the requested window
        if len(buffer) < offset + limit:
            need_more = (offset + limit) - len(buffer)
            if need_more > 0:
                buffer.extend(batch[:need_more])

        token = data.get("offset")
        if not token:
            break

    window = buffer[offset : offset + limit]
    return window, total_count


def update_airtable_record(record_id: str, relevance: str, subsystem: List[str], score: int) -> None:
    """
    Update an Airtable record with scoring results.
    """
    if not (AIRTABLE_API_KEY and AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME):
        raise RuntimeError("Airtable environment variables not configured")

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}"
    headers = _base_headers()
    data = {
        "fields": {
            "Relevance": relevance,
            "Subsystem": subsystem if subsystem else [],
            "Score": score,
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()
