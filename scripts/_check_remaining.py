#!/usr/bin/env python3
"""Check remaining untranslated values - writes to file."""
import json, os, re, sys

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

ACRONYMS = {"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI","SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD","RON","JSON","BOM","UTF-8","MB","MB.","AI","R&D","HQ","POD","ADR","EORI","COD","YTD","DDD","TGD","ZIP","L/100KM","EUR/KM"}
UPPER_ACRONYMS = {a.upper() for a in ACRONYMS}
KEEP_AS_ENGLISH = {"EUR","RON","GBP","USD","VIN","KM","PDF","CSV","JSON","N/A","OCR","GPS","API","CMR","KPI","SMTP"}

def is_untranslatable(val):
    if not isinstance(val, str) or not val:
        return True
    if re.match(r'^[\d\.,\s%\u20ac$\u00a3\u00b1\-—=\'\"\u2032\u2033]+$', val):
        return True
    if "@" in val and "." in val:
        return True
    if val in KEEP_AS_ENGLISH:
        return True
    if val.upper() in UPPER_ACRONYMS:
        return True
    return False

en_flat = flatten(en)

out = open(os.path.join(TRANS_DIR, "_remaining_report.txt"), "w", encoding="utf-8")

for lang in ["cs", "pt", "hu", "tr"]:
    data = json.load(open(os.path.join(TRANS_DIR, f"{lang}.json"), "r", encoding="utf-8-sig"))
    flat = flatten(data)
    
    untranslated = []
    for k in en_flat:
        en_v = en_flat[k]
        if not isinstance(en_v, str) or not en_v.strip():
            continue
        if k not in flat:
            continue
        v = flat[k]
        if not isinstance(v, str):
            continue
        if v == en_v and not is_untranslatable(en_v):
            untranslated.append((k, en_v))
    
    out.write(f"\n=== {lang}.json - {len(untranslated)} remaining untranslated ===\n")
    for k, v in untranslated[:200]:
        out.write(f"  {k}: {v}\n")
    if len(untranslated) > 200:
        out.write(f"  ... and {len(untranslated)-200} more\n")
    
    sections = {}
    for k, v in untranslated:
        sec = k.split(".")[0]
        sections[sec] = sections.get(sec, 0) + 1
    out.write("\n  By section:\n")
    for sec, count in sorted(sections.items(), key=lambda x: -x[1]):
        out.write(f"    {sec}: {count}\n")

out.close()
print("Report written to data/translations/_remaining_report.txt")
