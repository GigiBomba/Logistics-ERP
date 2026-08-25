#!/usr/bin/env python3
"""Analyze translation files for untranslated values."""
from __future__ import annotations

import json, os, re, sys

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def flatten(d, prefix=""):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.update(flatten(item, f"{key}[{i}]"))
                elif isinstance(item, str):
                    items[f"{key}[{i}]"] = item
                else:
                    items[f"{key}[{i}]"] = item
        else:
            items[key] = v
    return items

ACRONYMS = {
    "ID", "KM", "VIN", "EUR", "N/A", "CSV", "PDF", "OCR", "GPS",
    "API", "CMR", "KPI", "SMTP", "DSO", "SLA", "SOC", "GDPR", "CUI",
    "VAT", "ETA", "SMS", "GBP", "USD", "RON", "JSON", "BOM", "UTF-8",
    "MB", "MB.", "AI", "R&D", "HQ", "POD", "ADR", "EORI", "COD", "YTD",
    "DDD", "TGD", "ZIP", "L/100KM"
}

def is_pure_acronym(v):
    v = v.strip().replace("(", "").replace(")", "").replace(".", "").strip()
    return v in ACRONYMS or v.upper() in ACRONYMS

en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
en = json.load(open(en_path, "r", encoding="utf-8-sig"))
en_flat = flatten(en)

for lang in ["cs", "pt", "hu", "tr"]:
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    data = json.load(open(filepath, "r", encoding="utf-8-sig"))
    flat = flatten(data)
    
    untranslated = []
    translated_map = {}
    
    for k, en_v in en_flat.items():
        if k in flat:
            v = flat[k]
            if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                if v == en_v and not is_pure_acronym(v) and not re.match(r'^[\d\.,\s%€$£±\-─—=]+$', v) and "@" not in v:
                    untranslated.append((k, v))
                elif v != en_v:
                    translated_map[en_v] = v
    
    total = sum(1 for k, v in en_flat.items() if isinstance(v, str) and v.strip())
    print(f"\n{'='*60}")
    print(f"  {lang}.json Analysis")
    print(f"{'='*60}")
    print(f"  Total string values: {total}")
    print(f"  Untranslated: {len(untranslated)} ({len(untranslated)/total*100:.1f}%)")
    print(f"  Already translated: {len(translated_map)}")
    
    # Section breakdown
    sections = {}
    for k, v in untranslated:
        sec = k.split(".")[0]
        sections[sec] = sections.get(sec, 0) + 1
    
    print(f"\n  Untranslated by section:")
    for sec, count in sorted(sections.items(), key=lambda x: -x[1]):
        print(f"    {sec}: {count}")
    
    # Show some untranslated values
    print(f"\n  Sample untranslated (first 40):")
    for k, v in untranslated[:40]:
        print(f"    {k}: {repr(v)}")
    
    print()
