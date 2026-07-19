#!/usr/bin/env python3
"""Generate the final translate_batch4.py script."""
import os

# This script generates translate_batch4.py which loads dictionaries from batch4_dicts.json
# and applies them to all 4 translation files

script_content = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate ALL remaining English-matching values in uk.json, ru.json, es.json, de.json to 90%+ coverage."""
import json, os, re

DIR = "data/translations"
DICT_PATH = os.path.join(os.path.dirname(__file__), "batch4_dicts.json")

ACRONYMS = {"EUR","RON","USD","GBP","VAT","CMR","ADR","GPS","ERP","JSON","CSV","PDF",
    "HTML","XML","API","SMTP","OCR","AI","ID","DSO","KPI","ETA","EORI","VIN",
    "INV","COD","POD","TGD","DDD","YTD","ZIP","LKW","CUI","CASHFLOW",
    "OPERION","GRAPHOPPER","PADDLEOCR","GDPR","CEO"}

def flatten(d, p=""):
    items = {}
    for k, v in d.items():
        key = f"{p}.{k}" if p else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                items[f"{key}[{i}]"] = x
        else:
            items[key] = v
    return items

def count_english(en_flat, tflat):
    return sum(1 for k in en_flat if k in tflat and str(en_flat[k]).strip() == str(tflat[k]).strip())

def apply_dict(data, tmap, prefix=""):
    if isinstance(data, dict):
        return {k: apply_dict(v, tmap, f"{prefix}.{k}" if prefix else k) for k, v in data.items()}
    elif isinstance(data, list):
        return [apply_dict(v, tmap, prefix) for v in data]
    elif isinstance(data, str) and data in tmap:
        return tmap[data]
    return data

def main():
    en = json.load(open(os.path.join(DIR, "en.json"), encoding="utf-8"))
    en_flat = flatten(en)
    
    # Load pre-built dictionaries
    if os.path.exists(DICT_PATH):
        all_dicts = json.load(open(DICT_PATH, encoding="utf-8"))
    else:
        all_dicts = {}
    
    targets = ["uk", "ru", "es", "de"]
    results = {}
    
    for lang in targets:
        path = os.path.join(DIR, f"{lang}.json")
        data = json.load(open(path, encoding="utf-8"))
        flat = flatten(data)
        
        # Build base translation map from existing translated values
        tmap = {}
        for k in en_flat:
            if k in flat:
                ev = str(en_flat[k]).strip()
                tv = str(flat[k]).strip()
                if ev != tv and ev and tv:
                    tmap[ev] = tv
        
        # Merge with pre-built dictionary
        if lang in all_dicts:
            tmap.update(all_dicts[lang])
        
        before = count_english(en_flat, flat)
        total = sum(1 for k in en_flat if k in flat)
        pct_before = before / total * 100 if total else 0
        print(f"[{lang}] Before: {before}/{total} English ({pct_before:.1f}%)")
        
        new_data = apply_dict(data, tmap)
        new_flat = flatten(new_data)
        after = count_english(en_flat, new_flat)
        pct_after = after / total * 100 if total else 0
        print(f"[{lang}] After: {after}/{total} English ({pct_after:.1f}%)")
        
        covered = total - after
        pct = covered / total * 100 if total else 0
        print(f"[{lang}] Coverage: {pct:.1f}%")
        results[lang] = pct
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    
    print("\n" + "="*50)
    for lang, pct in results.items():
        print(f"  {lang}.json: {pct:.1f}% coverage")
    print("="*50)

if __name__ == "__main__":
    main()
'''

with open(os.path.join("scripts", "translate_batch4.py"), "w", encoding="utf-8") as f:
    f.write(script_content)

print("translate_batch4.py generated successfully")
