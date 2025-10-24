"""Test Airtable fetch_records function directly."""
import sys
sys.path.insert(0, '.')

from api import airtable_service

try:
    print("Testing fetch_records...")
    records, total = airtable_service.fetch_records(limit=5, offset=0)
    print(f"Total records: {total}")
    print(f"Returned: {len(records)} records")
    if records:
        print(f"\nFirst record fields:")
        for key, value in records[0].items():
            print(f"  {key}: {type(value).__name__} = {value if not isinstance(value, str) or len(value) < 100 else value[:100] + '...'}")
    else:
        print("No records returned")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
