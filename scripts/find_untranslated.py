#!/usr/bin/env python3
"""Step 1: Find all untranslated keys and generate translation map."""
from __future__ import annotations

import json, os

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def flat(d, pfx=""):
    r = {}
    for k, v in d.items():
        pk = f"{pfx}.{k}" if pfx else k
        if isinstance(v, dict): r.update(flat(v, pk))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                r[f"{pk}[{i}]"] = item
        else: r[pk] = v
    return r

with open(os.path.join(TRANS_DIR, "de.json"), "r", encoding="utf-8") as f:
    de_data = json.load(f)
with open(os.path.join(TRANS_DIR, "en.json"), "r", encoding="utf-8") as f:
    en_data = json.load(f)

de_flat = flat(de_data)
en_flat = flat(en_data)

untranslated = {}
for k in sorted(en_flat.keys()):
    if k in de_flat and str(de_flat[k]) == str(en_flat[k]):
        val = str(en_flat[k])
        if val and val not in ("EUR","RON","USD","GBP","ID","N/A","VIN:"):
            untranslated[k] = val

print(f"Untranslated keys: {len(untranslated)}")
print(f"\n--- VALUES TO TRANSLATE ---")
for k, v in untranslated.items():
    print(json.dumps(v))
