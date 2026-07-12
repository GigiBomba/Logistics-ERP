#!/usr/bin/env python3
"""Translate English placeholder values in de.json to German."""
import json, os, sys

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def flat(d, pfx=""):
    r = {}
    for k, v in d.items():
        pk = f"{pfx}.{k}" if pfx else k
        if isinstance(v, dict): r.update(flat(v, pk))
        else: r[pk] = v
    return r

def unflat(items):
    r = {}
    for p, v in items.items():
        parts = p.split(".")
        cur = r
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = v
    return r

def main():
    de_path = os.path.join(TRANS_DIR, "de.json")
    en_path = os.path.join(TRANS_DIR, "en.json")
    map_path = os.path.join(TRANS_DIR, "de_translation_map.json")

    with open(de_path, "r", encoding="utf-8") as f: de_data = json.load(f)
    with open(en_path, "r", encoding="utf-8") as f: en_data = json.load(f)
    with open(map_path, "r", encoding="utf-8") as f: en2de = json.load(f)

    de_flat = flat(de_data)
    en_flat = flat(en_data)
    changed = 0
    skipped = 0
    not_found = []

    for key in en_flat:
        if key not in de_flat:
            continue
        en_val = str(en_flat[key])
        de_val = str(de_flat[key])
        if en_val == de_val and en_val in en2de:
            de_flat[key] = en2de[en_val]
            changed += 1
        elif en_val == de_val:
            skipped += 1
            not_found.append(key)

    result = unflat(de_flat)
    with open(de_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Changed: {changed}")
    print(f"Skipped (no mapping): {skipped}")
    if not_found:
        print(f"First 20 missing keys:")
        for k in not_found[:20]:
            print(f"  {k} = {de_flat[k][:60]}")

if __name__ == "__main__":
    main()
