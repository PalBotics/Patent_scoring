USPTO ODP Bulk Abstract Extractor
================================

This script parses USPTO ODP bulk XML files (pre-grant and grants) to extract:
- document number, kind, date, country
- title
- abstract (full; plus a truncated version for CSV/Airtable)
- CPC codes
- applicants and assignees

It is memory-efficient (iterparse) and supports .xml, .gz, and .zip files.

Examples
--------
# Single ZIP containing many XMLs
python odp_bulk_abstracts_extract.py --input /path/pgpubs-2025-09-XML.zip --out-jsonl abstracts.jsonl --out-csv abstracts.csv --sqlite patents.db

# Directory of XMLs
python odp_bulk_abstracts_extract.py --input /path/to/xml_dir --out-jsonl abstracts.jsonl

# Single large XML.gz
python odp_bulk_abstracts_extract.py --input /path/grants-2024-XML.gz --out-jsonl abstracts.jsonl --out-csv abstracts.csv

Notes
-----
- The CSV includes the abstract truncated to 2000 chars, suitable for Airtable.
- The JSONL and SQLite store full abstracts for downstream use.
- You can adjust --truncate to any character limit you prefer.
