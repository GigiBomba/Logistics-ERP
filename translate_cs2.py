#!/usr/bin/env python3
"""
Comprehensive translation of cs.json - translate ALL remaining English values to Czech.
"""
import json
import os
import re

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data', 'translations')

with open(os.path.join(data_dir, 'en.json'), 'r', encoding='utf-8') as f:
    en_data = json.load(f)

with open(os.path.join(data_dir, 'cs.json'), 'r', encoding='utf-8') as f:
    cs_data = json.load(f)

CZECH_CHARS = set('ěščřžýáíéúůďťňóĚŠČŘŽÝÁÍÉÚŮĎŤŇÓ')

def looks_czech(val):
    if not isinstance(val, str): return False
    return bool(CZECH_CHARS & set(val))

# Collect all en -> cs pairs that are still English
def collect_untranslated(en_obj, cs_obj, path='', result=None):
    if result is None: result = {}
    if isinstance(en_obj, dict) and isinstance(cs_obj, dict):
        for k in en_obj:
            if k in cs_obj:
                collect_untranslated(en_obj[k], cs_obj[k], f'{path}.{k}', result)
    elif isinstance(en_obj, list) and isinstance(cs_obj, list):
        for i in range(min(len(en_obj), len(cs_obj))):
            collect_untranslated(en_obj[i], cs_obj[i], f'{path}[{i}]', result)
    elif isinstance(en_obj, str) and isinstance(cs_obj, str):
        if cs_obj == en_obj and en_obj != '' and not looks_czech(en_obj):
            # Check if it's not an acronym
            words = en_obj.split()
            acronyms_only = all(
                w.strip('.,:;()[]{}!?/%-─— ') in {'ID','KM','VIN','EUR','N/A','CSV','PDF','OCR','GPS','API','CMR','KPI','SMTP','DSO','SLA','SOC','GDPR','CUI','VAT','ETA','SMS','GBP','USD','RON','JSON','BOM','UTF-8','L/100km','€','h','min','L'}
                or not any(c.isalpha() for c in w)
                or w.strip('.,:;()[]{}!?/%-─— ').isdigit()
                for w in words if w.strip('.,:;()[]{}!?/%-─— ')
            )
            if not acronyms_only and en_obj not in {'─'*50}:
                result[path] = en_obj
    return result

untranslated = collect_untranslated(en_data, cs_data)
print(f"Total untranslated strings: {len(untranslated)}")

# Show all unique strings
unique_strings = sorted(set(untranslated.values()))
for s in unique_strings:
    print(repr(s))
