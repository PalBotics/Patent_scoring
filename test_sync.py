#!/usr/bin/env python3
"""Test Airtable sync logic"""
import sys
sys.path.insert(0, '.')

from api.db import SessionLocal
from api.models import Score
from api import airtable_service
import requests
import urllib.parse

db = SessionLocal()
try:
    # Get a High scored patent
    score = db.query(Score).filter(Score.relevance == 'High').first()
    if not score:
        print("No High-scored patents found")
        sys.exit(1)
    
    print(f"Testing with patent: {score.patent_id}")
    
    # Test lookup
    base = airtable_service.AIRTABLE_BASE_ID
    table = airtable_service.AIRTABLE_TABLE_NAME
    headers = airtable_service._base_headers()
    
    formula = urllib.parse.quote("{Patent ID}='" + score.patent_id.replace("'", "\\'") + "'")
    list_url = f"https://api.airtable.com/v0/{base}/{table}?maxRecords=1&filterByFormula={formula}"
    
    print(f"Checking if exists in Airtable...")
    resp = requests.get(list_url, headers=headers)
    print(f"Lookup status: {resp.status_code}")
    
    if resp.ok:
        records = resp.json().get('records', [])
        print(f"Existing records: {len(records)}")
        
        if records:
            print(f"Already in Airtable: {records[0]['id']}")
        else:
            print("Not in Airtable - attempting to create...")
            # Actually try to create
            fields = {
                "Patent ID": score.patent_id,
                "Abstract": getattr(score, "abstract", "") or "",
                "Relevance": score.relevance,
                "Subsystem": [],
                "Publication Date": getattr(score, "pub_date", "") or "",
            }
            title = getattr(score, "title", None)
            if title:
                fields["Title"] = title
            create_url = f"https://api.airtable.com/v0/{base}/{table}"
            create_resp = requests.post(create_url, headers=headers, json={"fields": fields})
            print(f"Create status: {create_resp.status_code}")
            if create_resp.ok:
                print(f"SUCCESS! Created record: {create_resp.json()['id']}")
            else:
                print(f"ERROR: {create_resp.text}")
    else:
        print(f"ERROR: {resp.status_code} - {resp.text}")
        
finally:
    db.close()
