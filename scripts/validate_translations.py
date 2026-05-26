"""Translation validation utility.
Compares all language files against English base.
Reports missing keys, coverage %, and structural issues.
"""
import json, os, sys

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def flatten(d, prefix=""):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            items[key] = json.dumps(v)
        else:
            items[key] = str(v)
    return items

def main():
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    if not os.path.isfile(en_path):
        print(f"ERROR: English base not found at {en_path}")
        sys.exit(1)

    en_flat = flatten(load_json(en_path))
    en_count = len(en_flat)
    en_keys = set(en_flat.keys())
    print(f"English base: {en_count} keys\n")

    for fname in sorted(os.listdir(TRANSLATIONS_DIR)):
        if not fname.endswith(".json"):
            continue
        code = fname[:-5]
        path = os.path.join(TRANSLATIONS_DIR, fname)
        try:
            raw = load_json(path)
        except json.JSONDecodeError as e:
            print(f"  INVALID JSON  {fname}: {e}")
            continue

        lang_flat = flatten(raw)
        lang_keys = set(lang_flat.keys())
        translated = sum(1 for k in en_keys if k in lang_keys and lang_flat[k] != en_flat[k])
        missing_in_lang = en_keys - lang_keys
        extra = lang_keys - en_keys
        coverage = translated / en_count * 100

        status = "OK" if coverage > 0 else "EMPTY"
        print(f"  {fname:20s} {translated:3d}/{en_count} ({coverage:5.1f}%)  {status}")
        if missing_in_lang:
            for k in sorted(missing_in_lang):
                print(f"    MISSING: {k}")
        if extra:
            for k in sorted(extra):
                print(f"    EXTRA:   {k}")

    print("\nDone.")

if __name__ == "__main__":
    main()
