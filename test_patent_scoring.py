import os
import unittest
import json
import sqlite3
from pathlib import Path
import csv

# Ensure required env vars are set for import
os.environ.setdefault('AIRTABLE_API_KEY', 'test')
os.environ.setdefault('AIRTABLE_BASE_ID', 'test')
os.environ.setdefault('AIRTABLE_TABLE_NAME', 'Patents')
os.environ.setdefault('OPENAI_API_KEY', 'test')

import importlib.util
spec = importlib.util.spec_from_file_location('patent_scoring', 'patent_scoring.py')
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

class PatentScoringTests(unittest.TestCase):
    def setUp(self):
        # Use a temporary DB
        self.db_path = Path('patent_scores.db')
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                # If file is locked, leave it and proceed (tests will use existing DB)
                pass
        self.conn = ps.init_db()

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        if self.db_path.exists():
            try:
                self.db_path.unlink()
            except PermissionError:
                pass
        # Remove scored CSV if created
        scored = Path('sample_patents.scored.csv')
        if scored.exists():
            scored.unlink()

    def test_read_local_file_csv(self):
        records = ps.read_local_file('sample_patents.csv')
        self.assertEqual(len(records), 5)
        self.assertEqual(records[0]['patent_id'], 'P1')

    def test_mapping_load_and_score(self):
        mapping = ps.load_mapping_from_file('example_mapping.json')
        # Test scoring P1 which should match Detection
        rec = ps.read_local_file('sample_patents.csv')[0]
        res = ps.keyword_score(rec['title'], rec['abstract'], mapping=mapping)
        self.assertIn('Detection', res['Subsystem'])
        self.assertIn(res['Relevance'], ['High', 'Medium', 'Low'])

    def test_store_and_check_cache(self):
        rec = ps.read_local_file('sample_patents.csv')[0]
        sha1 = ps.compute_sha1(rec['patent_id'], rec['abstract'])
        ps.store_result(self.conn, rec['patent_id'], sha1, 'High', ['Detection'], rec['title'], rec['abstract'], 'test')
        cached = ps.check_if_scored(self.conn, rec['patent_id'], sha1)
        self.assertIsNotNone(cached)
        self.assertEqual(cached[0], 'High')

    def test_local_run_export(self):
        # Simulate local mode processing using example mapping and sample csv
        mapping = ps.load_mapping_from_file('example_mapping.json')
        records = ps.read_local_file('sample_patents.csv')
        results = []
        for i, p in enumerate(records, 1):
            pid = p.get('patent_id') or f'local-{i}'
            title = p.get('title','')
            abstract = p.get('abstract','')
            sha1 = ps.compute_sha1(pid, abstract)
            cached = ps.check_if_scored(self.conn, pid, sha1)
            if cached:
                relevance, subsystem = cached
            else:
                score = ps.keyword_score(title, abstract, mapping=mapping)
                relevance = score['Relevance']
                subsystem = score['Subsystem']
                ps.store_result(self.conn, pid, sha1, relevance, subsystem, title, abstract, 'local-keyword')
            results.append({'patent_id': pid, 'title': title, 'abstract': abstract, 'relevance': relevance, 'subsystem': ';'.join(subsystem) if subsystem else ''})
        # Export
        out_csv = Path('sample_patents.scored.csv')
        with open(out_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['patent_id', 'title', 'abstract', 'relevance', 'subsystem'])
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        self.assertTrue(out_csv.exists())

if __name__ == '__main__':
    unittest.main()
