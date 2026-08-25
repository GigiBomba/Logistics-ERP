#!/usr/bin/env python3
"""Final coverage check."""
from __future__ import annotations

import json, os, re

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")
en = json.load(open(os.path.join(TRANS_DIR, "en.json"), "r", encoding="utf-8-sig"))

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

en_flat = flatten(en)

ACRONYMS = {"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI","SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD","RON","JSON","BOM","UTF-8","MB","MB.","AI","R&D","HQ","POD","ADR","EORI","COD","YTD","DDD","TGD","ZIP","L/100KM","EUR/KM"}
UPPER_ACRONYMS = {a.upper() for a in ACRONYMS}

def is_untranslatable(val):
    if not isinstance(val, str) or not val:
        return True
    if re.match(r"^[\d\.,\s%\u20ac$\u00a3\u00b1\-—=\'\"\u2032\u2033]+$", val):
        return True
    if "@" in val and "." in val:
        return True
    if val.upper() in UPPER_ACRONYMS:
        return True
    return False

total_strings = sum(1 for v in en_flat.values() if isinstance(v, str) and v.strip())
print(f"Total string values to translate: {total_strings}")
print()

for lang in ["cs", "pt", "hu", "tr"]:
    data = json.load(open(os.path.join(TRANS_DIR, f"{lang}.json"), "r", encoding="utf-8-sig"))
    flat = flatten(data)
    translated = 0
    for k in en_flat:
        en_v = en_flat[k]
        if not isinstance(en_v, str) or not en_v.strip():
            continue
        if k in flat:
            v = flat[k]
            if isinstance(v, str):
                if v != en_v or is_untranslatable(en_v):
                    translated += 1
    pct = translated / total_strings * 100
    print(f"  {lang}.json: {pct:.1f}% ({translated}/{total_strings})")

# Run validate
print()
import subprocess
result = subprocess.run(["python", "scripts/validate_translations.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print(result.stderr[:500])
