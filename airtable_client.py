import requests
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def fetch_unscored(base_id: str, table_name: str, api_key: str, batch_size: int = 100) -> List[Dict]:
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    params = {"filterByFormula": "AND({Relevance} = '', {Abstract} != '')",
              "fields": ["Patent ID", "Title", "Abstract", "Publication Date"],
              "maxRecords": batch_size,
              "sort": [{"field": "Patent ID", "direction": "asc"}]}
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
    logger.info(f"Fetched {len(batch_records)} records from Airtable")
    return batch_records


def update_record(base_id: str, table_name: str, api_key: str, record_id: str, relevance: str, subsystem: List[str]) -> None:
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {"fields": {"Relevance": relevance, "Subsystem": subsystem if subsystem else []}}
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()


def delete_record(base_id: str, table_name: str, api_key: str, record_id: str) -> None:
    url = f"https://api.airtable.com/v0/{base_id}/{table_name}/{record_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.delete(url, headers=headers)
    response.raise_for_status()
