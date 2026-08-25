#!/usr/bin/env python3
"""Comprehensive translation of es.json - translates all untranslated keys to Spanish."""
from __future__ import annotations

import json, os, re, shutil

BASE = os.path.join(os.path.dirname(__file__), os.pardir, "data", "translations")
ES_PATH = os.path.join(BASE, "es.json")
EN_PATH = os.path.join(BASE, "en.json")

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

def set_nested(d, key_parts, value):
    cur = d
    for p in key_parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[key_parts[-1]] = value

es_data = load_json(ES_PATH)
en_data = load_json(EN_PATH)
es_flat = flatten(es_data)
en_flat = flatten(en_data)

# Identify untranslated keys (es value == en value)
untranslated = {k for k in en_flat if k in es_flat and isinstance(es_flat[k], str) and es_flat[k] == en_flat[k] and not isinstance(en_flat[k], (list, dict))}

print(f"Untranslated keys: {len(untranslated)}")

# ============ COMPREHENSIVE PHRASE TRANSLATION MAP ============
P = {}
