
import os
import gzip
import json
import csv
import zipfile
import argparse
from xml.etree.ElementTree import iterparse

def _strip_ns(tag):
    return tag.split('}', 1)[-1] if '}' in tag else tag

def _text(elem):
    return (elem.text or '').strip() if elem is not None else ''

def _iter_children(elem, name):
    for child in elem:
        if _strip_ns(child.tag) == name:
            yield child

def extract_record(doc_elem):
    doc_tag = _strip_ns(doc_elem.tag)
    is_grant = 'grant' in doc_tag
    biblio = None
    for child in doc_elem:
        if _strip_ns(child.tag) in ['us-bibliographic-data-grant', 'us-bibliographic-data-application', 'bibliographic-data']:
            biblio = child
            break

    doc_number = kind = date = country = None
    if biblio is not None:
        for child in biblio.iter():
            if _strip_ns(child.tag) == 'document-id':
                for g in child:
                    gtag = _strip_ns(g.tag)
                    if gtag == 'doc-number':
                        doc_number = _text(g)
                    elif gtag == 'kind':
                        kind = _text(g)
                    elif gtag == 'date':
                        date = _text(g)
                    elif gtag == 'country':
                        country = _text(g)

    title = None
    for child in doc_elem:
        if _strip_ns(child.tag) == 'invention-title':
            title = _text(child)
            break

    abstract_text = None
    for child in doc_elem:
        if _strip_ns(child.tag) == 'abstract':
            paras = [''.join(p.itertext()).strip() for p in _iter_children(child, 'p')]
            abstract_text = '\\n\\n'.join(paras) if paras else ''.join(child.itertext()).strip()
            break

    return {
        'doc_type': 'grant' if is_grant else 'pregrant',
        'doc_number': doc_number,
        'kind': kind,
        'date': date,
        'country': country,
        'title': title,
        'abstract': abstract_text
    }

def parse_xml(stream, writer, truncate=2000):
    context = iterparse(stream, events=('start', 'end'))
    _, root = next(context)
    DOC_TAGS = {'us-patent-application', 'us-patent-grant', 'patent-application-publication', 'patent-grant'}
    count = 0
    for event, elem in context:
        if event == 'end' and _strip_ns(elem.tag) in DOC_TAGS:
            rec = extract_record(elem)
            if rec.get('abstract'):
                rec['abstract_truncated'] = rec['abstract'][:truncate]
            writer(rec)
            elem.clear()
            root.clear()
            count += 1
    return count

def process_input(input_path, out_jsonl=None, out_csv=None, truncate=2000):
    jsonl_f = open(out_jsonl, 'w', encoding='utf-8') if out_jsonl else None
    csv_f = open(out_csv, 'w', encoding='utf-8', newline='') if out_csv else None
    csv_w = csv.writer(csv_f) if csv_f else None
    if csv_w:
        csv_w.writerow(['doc_type','doc_number','kind','date','country','title','abstract_truncated'])

    def writer(rec):
        if jsonl_f:
            jsonl_f.write(json.dumps(rec, ensure_ascii=False) + '\\n')
        if csv_w:
            csv_w.writerow([rec.get('doc_type',''),rec.get('doc_number',''),rec.get('kind',''),
                            rec.get('date',''),rec.get('country',''),rec.get('title',''),
                            rec.get('abstract_truncated','')])

    total = 0
    if input_path.lower().endswith('.zip'):
        with zipfile.ZipFile(input_path, 'r') as z:
            for name in z.namelist():
                if name.lower().endswith(('.xml', '.gz')):
                    with z.open(name) as f:
                        if name.lower().endswith('.gz'):
                            with gzip.open(f) as gzf:
                                total += parse_xml(gzf, writer, truncate)
                        else:
                            total += parse_xml(f, writer, truncate)
    elif input_path.lower().endswith('.gz'):
        with gzip.open(input_path, 'rb') as f:
            total += parse_xml(f, writer, truncate)
    else:
        with open(input_path, 'rb') as f:
            total += parse_xml(f, writer, truncate)

    if jsonl_f: jsonl_f.close()
    if csv_f: csv_f.close()
    print(f"Done. Parsed {total} documents.")

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Extract abstracts from USPTO ODP bulk XML.')
    ap.add_argument('--input', required=True, help='Input .xml, .gz, or .zip path')
    ap.add_argument('--out-jsonl', help='Output JSONL path')
    ap.add_argument('--out-csv', help='Output CSV path')
    ap.add_argument('--truncate', type=int, default=2000, help='Truncate abstract length for CSV')
    args = ap.parse_args()
    process_input(args.input, args.out_jsonl, args.out_csv, args.truncate)
