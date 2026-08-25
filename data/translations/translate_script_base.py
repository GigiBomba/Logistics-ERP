from __future__ import annotations

import json, os, re, copy, sys

BASE = os.path.dirname(os.path.abspath(__file__))

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

def flatten(d, prefix=''):
    items = []
    if isinstance(d, dict):
        for k, v in d.items():
            np = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                items.extend(flatten(v, np))
            else:
                items.append((np, v))
    elif isinstance(d, list):
        for i, v in enumerate(d):
            np = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                items.extend(flatten(v, np))
            else:
                items.append((np, v))
    return items

def set_nested(d, key_path, value):
    parts = re.findall(r'([^.\[\]]+)|\[(\d+)\]', key_path)
    for i, (key, idx) in enumerate(parts):
        k = key if key else int(idx)
        if i == len(parts) - 1:
            d[k] = value
        else:
            d = d[k]

def translate_file(en_data, target_data, trans_map, file_label):
    en_flat = dict(flatten(en_data))
    target_flat = dict(flatten(target_data))
    translated = 0
    untranslated_count = 0
    for key_path, en_val in en_flat.items():
        if key_path in target_flat:
            t_val = target_flat[key_path]
            if isinstance(t_val, str) and t_val == en_val and isinstance(en_val, str):
                if en_val in trans_map:
                    set_nested(target_data, key_path, trans_map[en_val])
                    translated += 1
                else:
                    untranslated_count += 1
    return translated, untranslated_count

# Load translations from external file
# We'll load the translation maps from JSON files
