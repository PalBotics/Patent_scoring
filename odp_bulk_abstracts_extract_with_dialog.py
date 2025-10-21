
import os
import gzip
import json
import csv
import zipfile
import argparse
import tkinter as tk
from tkinter import filedialog
from xml.etree.ElementTree import iterparse, ParseError
import io
import tempfile

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

def _parse_single_xml_stream(stream, writer, truncate, DOC_TAGS):
    """Parse a single well-formed XML document from a seekable/buffered stream."""
    context = iterparse(stream, events=('start', 'end'))
    _, root = next(context)
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


def _iter_concatenated_docs(stream, xml_decl=b'<?xml', chunk_size=65536):
    """Yield byte segments each beginning with an XML declaration where possible.

    This reads the provided (seekable) binary stream in chunks and splits on the
    XML declaration token. It yields segments as bytes suitable for parsing
    independently (wrapped into BytesIO).
    """
    buf = b''
    while True:
        data = stream.read(chunk_size)
        if not data:
            if buf:
                yield buf
            break
        buf += data
        # find subsequent declarations (skip possible declaration at position 0)
        while True:
            idx = buf.find(xml_decl, 1)
            if idx == -1:
                break
            # emit up to the next declaration
            yield buf[:idx]
            buf = buf[idx:]


def parse_xml(stream, writer, truncate=2000):
    DOC_TAGS = {'us-patent-application', 'us-patent-grant', 'patent-application-publication', 'patent-grant'}

    # Ensure we can seek/rewind the stream for retry attempts. If the provided
    # stream isn't seekable (for example, some zip/gzip file objects), copy to
    # a temporary file on disk which is seekable.
    need_close = False
    try:
        stream.seek(0)
        seekable = True
    except Exception:
        seekable = False

    if not seekable:
        tmp = tempfile.TemporaryFile()
        # copy all data into the tempfile
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.seek(0)
        stream = tmp
        need_close = True

    # Primary attempt: normal iterparse for a single well-formed document
    try:
        stream.seek(0)
        return _parse_single_xml_stream(stream, writer, truncate, DOC_TAGS)
    except ParseError as e:
        msg = str(e)
        # If it's a common concatenated-docs/junk-after-root issue, try a
        # streaming fallback that splits on XML declarations and parses each
        # document separately.
        if 'junk after document element' not in msg and 'multiple document' not in msg:
            # re-raise unexpected parse errors
            if need_close:
                stream.close()
            raise

    # Fallback: split the data into segments that look like separate XML docs
    total = 0
    stream.seek(0)
    for seg in _iter_concatenated_docs(stream):
        seg = seg.strip()
        if not seg:
            continue
        # ensure the segment starts with an XML declaration; if it doesn't,
        # try to add one (this is conservative - most ODP files start with one)
        if not seg.startswith(b'<?xml'):
            # try to find the first '<' and start from there
            idx = seg.find(b'<')
            if idx > 0:
                seg = seg[idx:]
        bio = io.BytesIO(seg)
        try:
            total += _parse_single_xml_stream(bio, writer, truncate, DOC_TAGS)
        except ParseError:
            # As a last-resort for a resistant segment, try wrapping it in a
            # synthetic root (removing any XML declarations) and parse.
            try:
                text = seg
                # remove XML declarations
                while text.lstrip().startswith(b'<?xml'):
                    p = text.find(b'?>')
                    if p == -1:
                        break
                    text = text[p+2:]
                wrapped = b'<root>' + text + b'</root>'
                bio2 = io.BytesIO(wrapped)
                total += _parse_single_xml_stream(bio2, writer, truncate, DOC_TAGS)
            except Exception:
                # give up on this segment
                continue

    if need_close:
        stream.close()
    return total

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

def main():
    ap = argparse.ArgumentParser(description='Extract abstracts from USPTO ODP bulk XML.')
    ap.add_argument('--input', help='Input .xml, .gz, or .zip path')
    ap.add_argument('--out-jsonl', help='Output JSONL path')
    ap.add_argument('--out-csv', help='Output CSV path')
    ap.add_argument('--truncate', type=int, default=2000, help='Truncate abstract length for CSV')
    args = ap.parse_args()

    # File picker if no input provided
    if not args.input:
        root = tk.Tk()
        root.withdraw()
        args.input = filedialog.askopenfilename(
            title="Select USPTO bulk file (.zip, .gz, .xml)",
            filetypes=[("Patent files", "*.zip *.gz *.xml"), ("All files", "*.*")]
        )
        if not args.input:
            print("No file selected. Exiting.")
            return

    # Auto-generate output paths if not provided
    base = os.path.splitext(args.input)[0]
    if not args.out_jsonl:
        args.out_jsonl = base + "_abstracts.jsonl"
    if not args.out_csv:
        args.out_csv = base + "_abstracts.csv"

    print(f"Processing file: {args.input}")
    print(f"Output JSONL: {args.out_jsonl}")
    print(f"Output CSV: {args.out_csv}")

    process_input(args.input, args.out_jsonl, args.out_csv, args.truncate)

if __name__ == '__main__':
    main()
