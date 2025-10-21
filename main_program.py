import argparse
from pathlib import Path
import logging
from db import init_db, compute_sha1, store_result, check_if_scored
from local_io import select_local_file, read_local_file, load_mapping_from_file, prompt_for_subsystem_mapping, edit_mapping_dialog, save_mapping_to_file
from scorer import keyword_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true')
    parser.add_argument('--mapping-file', type=str, default=None)
    parser.add_argument('--input-file', type=str, default=None)
    return parser.parse_args()


def run_local(input_file: str = None, mapping_file: str = None):
    mapping = {}
    if mapping_file:
        mapping = load_mapping_from_file(mapping_file)
    else:
        mapping = prompt_for_subsystem_mapping()
        mapping = edit_mapping_dialog(mapping)
    if not input_file:
        input_file = select_local_file()
    records = read_local_file(input_file)

    conn = init_db()
    results = []
    for i, p in enumerate(records, 1):
        pid = p.get('patent_id') or f'local-{i}'
        title = p.get('title','')
        abstract = p.get('abstract','')
        sha1 = compute_sha1(pid, abstract)
        cached = check_if_scored(conn, pid, sha1)
        if cached:
            relevance, subsystem = cached
        else:
            score = keyword_score(title=title, abstract=abstract, mapping=mapping)
            relevance = score['Relevance']
            subsystem = score['Subsystem']
            store_result(conn, pid, sha1, relevance, subsystem, title, abstract, 'local-keyword')
        results.append({'patent_id': pid, 'title': title, 'abstract': abstract, 'relevance': relevance, 'subsystem': ';'.join(subsystem) if subsystem else ''})

    out_csv = Path(input_file).with_suffix('.scored.csv')
    import csv
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['patent_id','title','abstract','relevance','subsystem'])
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    logger.info(f"Wrote results to {out_csv}")


if __name__ == '__main__':
    args = parse_args()
    if args.local:
        run_local(input_file=args.input_file, mapping_file=args.mapping_file)
    else:
        print('Run with --local for local mode')
