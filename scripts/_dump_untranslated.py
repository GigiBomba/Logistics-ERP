#!/usr/bin/env python3
"""Dump all untranslated values for all 4 languages."""
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
    "DDD", "TGD", "ZIP", "L/100KM",
}

def is_untranslatable(val):
    if not isinstance(val, str) or not val:
        return True
    if re.match(r'^[\d\.,\s%€$£±\-─—=]+$', val):
        return True
    if val.startswith(('SELECT ', 'SELECT *', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')):
        return True
    if '@' in val and '.' in val:
        return True
    if val.upper() in ACRONYMS:
        return True
    return False

en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
en = json.load(open(en_path, "r", encoding="utf-8-sig"))
en_flat = flatten(en)

for lang in ["cs", "pt", "hu", "tr"]:
    filepath = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
    data = json.load(open(filepath, "r", encoding="utf-8-sig"))
    flat = flatten(data)
    
    untranslated = []
    for k, en_v in en_flat.items():
        if k in flat:
            v = flat[k]
            if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                if v == en_v and not is_untranslatable(v):
                    untranslated.append((k, v))
    
    # Write to file
    outpath = os.path.join(TRANSLATIONS_DIR, f"_{lang}_untranslated.txt")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(f"Total untranslated: {len(untranslated)}\n\n")
        for k, v in untranslated:
            f.write(f"{k}\t{v}\n")
    print(f"Wrote {len(untranslated)} untranslated values for {lang} -> {outpath}")
