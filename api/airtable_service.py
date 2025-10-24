import os
import requests
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Patents')


def _base_headers() -> Dict[str, str]:
    return {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}',
        'Content-Type': 'application/json',
    }


def fetch_records(limit: int = 25, offset: int = 0) -> Tuple[List[Dict], int]:
    """Fetch a slice of records from Airtable, approximating total.
    - limit: number of records to return
    - offset: zero-based index into the full record list
    Returns (records, total_estimate)
    """
    url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}'
    headers = _base_headers()

    collected: List[Dict] = []
    seen = 0
    token: Optional[str] = None
    page_size = 100  # Airtable max page size
    has_more = False

    while True:
        params: Dict[str, str | int] = {
            'pageSize': page_size,
            'sort[0][field]': 'Patent ID',
            'sort[0][direction]': 'asc',
        }
        if token:
            params['offset'] = token

        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

        batch = []
        for record in data.get('records', []):
            fields = record.get('fields', {})
            batch.append({
                'id': record.get('id', ''),
                'patent_id': fields.get('Patent ID', ''),
                'title': fields.get('Title', ''),
                'abstract': fields.get('Abstract', ''),
                'relevance': fields.get('Relevance'),
                'subsystem': fields.get('Subsystem', []),
                'pub_date': fields.get('Publication Date', ''),
            })

        seen += len(batch)
        collected.extend(batch)

        # Stop once we have enough to satisfy the requested window
        if len(collected) >= offset + limit:
            has_more = 'offset' in data
            break

        if 'offset' in data:
            token = data['offset']
        else:
            has_more = False
            break

    slice_start = offset
    slice_end = offset + limit
    window = collected[slice_start:slice_end]

    # Estimate total: what we've covered plus 1 if Airtable indicated more
    total_estimate = offset + len(window) + (1 if has_more else 0)
    return window, total_estimate


def update_airtable_record(record_id: str, relevance: str, subsystem: List[str], score: int) -> None:
    """Update an Airtable record with scoring results."""
    url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}/{record_id}'
    headers = _base_headers()
    data = {
        'fields': {
            'Relevance': relevance,
            'Subsystem': subsystem if subsystem else [],
            'Score': score,
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()
