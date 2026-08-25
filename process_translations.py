#!/usr/bin/env python3
"""
Universal translation processor.
Loads translation map from _tr_{lang}.json and applies to {lang}.json.
"""
from __future__ import annotations

import json, os, sys

BASE = r"C:\Users\Bonjo\source\repos\Calculator logistica\data\translations"
ACR = frozenset({"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI","SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD","RON","JSON","BOM","UTF-8","N/D","DDD","TGD","POD","EORI","ADR","YTD","ZIP","INV-","LIVE","COD","MB","ERP","L/100km"})

def load(p):
    with open(p, 'r', encoding='utf-8') as f: return json.load(f)
def save(p, d):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')

def flatten(d, pk=''):
    r = {}
    if isinstance(d, dict):
        for k, v in d.items():
            nk = f"{pk}.{k}" if pk else k
            if isinstance(v, dict): r.update(flatten(v, nk))
            else: r[nk] = v
    return r

def unflatten(d):
    r = {}
    for pk, v in d.items():
        parts = pk.split('.')
        cur = r
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = v
    return r

if len(sys.argv) < 2:
    print("Usage: python process_translations.py <lang_code>")
    print("  Reads _tr_<lang>.json and applies to <lang>.json")
    sys.exit(1)

lang = sys.argv[1]
tr_file = os.path.join(BASE, f'_tr_{lang}.json')

if not os.path.exists(tr_file):
    print(f"Translation file {tr_file} not found!")
    sys.exit(1)

en = load(os.path.join(BASE, 'en.json'))
target = load(os.path.join(BASE, f'{lang}.json'))
tr = load(tr_file)

en_f = flatten(en)
target_f = flatten(target)

total = sum(1 for k in en_f if k in target_f)
before = sum(1 for k, ev in en_f.items() if k in target_f 
             and isinstance(ev, str) and target_f[k] == ev 
             and ev.strip() not in ACR)

print(f"Before: {before}/{total} ({100*(total-before)/total:.1f}%)")

cnt = 0
for k, ev in en_f.items():
    if k in target_f:
        tv = target_f[k]
        if isinstance(ev, str) and tv == ev and ev in tr:
            target_f[k] = tr[ev]
            cnt += 1

new_data = unflatten(target_f)
save(os.path.join(BASE, f'{lang}.json'), new_data)

# Verify
v = load(os.path.join(BASE, f'{lang}.json'))
v_f = flatten(v)
after = sum(1 for k, ev in en_f.items() if k in v_f 
            and isinstance(ev, str) and v_f[k] == ev 
            and ev.strip() not in ACR)

try:
    js = json.dumps(new_data, ensure_ascii=False, indent=2) + '\n'
    json.loads(js)
    valid = True
except:
    valid = False

print(f"Translated: {cnt}")
print(f"After: {after}/{total} ({100*(total-after)/total:.1f}%)")
print(f"JSON valid: {valid}")
