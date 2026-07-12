#!/usr/bin/env python3
"""Translate all English placeholder values in de.json to German."""
import json
import os
import re

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def flatten_with_path(d, prefix=""):
    items = {}
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_with_path(v, path))
        else:
            items[path] = v
    return items

def unflatten(items):
    result = {}
    for path, value in items.items():
        parts = path.split(".")
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    return result
