from pathlib import Path
from typing import Dict, List
import csv
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog, simpledialog
import json


def select_local_file() -> str:
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select CSV or XML file",
        filetypes=[("CSV files", "*.csv"), ("XML files", "*.xml"), ("All files", "*")]
    )
    root.destroy()
    return file_path or ''


def read_local_file(file_path: str) -> List[Dict]:
    records = []
    p = Path(file_path)
    if p.suffix.lower() == '.csv':
        with open(file_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                records.append({
                    'id': f'local-{i}',
                    'patent_id': row.get('Patent ID') or row.get('patent_id') or '',
                    'title': row.get('Title') or row.get('title') or '',
                    'abstract': row.get('Abstract') or row.get('abstract') or ''
                })
    elif p.suffix.lower() == '.xml':
        tree = ET.parse(file_path)
        root = tree.getroot()
        # Attempt to find patent-like entries
        for i, entry in enumerate(root.findall('.//record') or root, 1):
            patent_id = entry.findtext('PatentID') or entry.findtext('PatentId') or entry.findtext('Patent_ID') or entry.findtext('PatentID') or ''
            title = entry.findtext('Title') or entry.findtext('title') or ''
            abstract = entry.findtext('Abstract') or entry.findtext('abstract') or ''
            records.append({
                'id': f'local-{i}',
                'patent_id': patent_id,
                'title': title,
                'abstract': abstract
            })
    else:
        raise ValueError('Unsupported file type')
    return records


def prompt_for_subsystem_mapping() -> Dict[str, List[str]]:
    root = tk.Tk()
    root.withdraw()
    mapping_text = simpledialog.askstring(
        "Subsystem Mapping",
        "Enter subsystem mappings, one per line, e.g.\nDetection: radar, lidar\nAI/Fusion: neural, fusion"
    )
    root.destroy()
    mapping = {}
    if not mapping_text:
        return mapping
    for line in mapping_text.splitlines():
        if ':' not in line:
            continue
        subsystem, keys = line.split(':', 1)
        kws = [k.strip().lower() for k in keys.split(',') if k.strip()]
        if kws:
            mapping[subsystem.strip()] = kws
    return mapping


def edit_mapping_dialog(initial_mapping: Dict[str, List[str]]) -> Dict[str, List[str]]:
    text = ''
    for k, kws in initial_mapping.items():
        text += f"{k}: {', '.join(kws)}\n"

    root = tk.Tk()
    root.withdraw()
    edited = simpledialog.askstring("Edit Mapping", "Edit subsystem mappings:", initialvalue=text)
    root.destroy()
    if not edited:
        return initial_mapping
    # Parse edited mapping
    new_map = {}
    for line in edited.splitlines():
        if ':' not in line:
            continue
        subsystem, keys = line.split(':', 1)
        kws = [k.strip().lower() for k in keys.split(',') if k.strip()]
        if kws:
            new_map[subsystem.strip()] = kws
    return new_map


def save_mapping_to_file(mapping: Dict[str, List[str]], path: str) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)


def load_mapping_from_file(path: str) -> Dict[str, List[str]]:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    normalized = {k: [kw.strip().lower() for kw in v] for k, v in data.items()}
    return normalized
