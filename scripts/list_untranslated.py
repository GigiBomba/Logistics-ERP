#!/usr/bin/env python3
"""List all untranslated keys and their values from es.json vs en.json."""
from __future__ import annotations

import json, os

BASE = os.path.join(os.path.dirname(__file__), os.pardir, "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def flatten(d, prefix=""):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = v
    return items

es_data = load_json(os.path.join(BASE, "es.json"))
en_data = load_json(os.path.join(BASE, "en.json"))
es_flat = flatten(es_data)
en_flat = flatten(en_data)

untranslated = sorted([k for k in en_flat if k in es_flat and isinstance(es_flat[k], str) and es_flat[k] == en_flat[k]])
print(f"Total untranslated: {len(untranslated)}")
print("---")
for k in untranslated:
    print(f"{k}\t{en_flat[k]}")
