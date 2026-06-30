#!/usr/bin/env python3
"""Validate all translation JSON files.

Checks:
  - valid JSON
  - UTF-8 encoding (no BOM)
  - required top-level sections
  - missing keys compared to en.json
  - placeholder consistency

Usage:
    python scripts/validate_translations.py
"""
import json
import os
import re
import sys
from typing import Dict, List, Tuple


TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

REQUIRED_SECTIONS = {"language_name", "app", "nav", "main", "fleet", "history", "settings"}


def load_json(path: str, strip_bom: bool = True) -> dict:
    encoding = "utf-8-sig" if strip_bom else "utf-8"
    with open(path, "r", encoding=encoding) as f:
        return json.load(f)


def flatten(d: dict, prefix: str = "") -> Dict[str, object]:
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = v
    return items


def extract_placeholders(text: str) -> List[str]:
    return re.findall(r"\{[^}]*\}", text) if isinstance(text, str) else []


def detect_bom(path: str) -> bool:
    with open(path, "rb") as f:
        raw = f.read(3)
    return raw == b"\xef\xbb\xbf"


def validate_file(filepath: str) -> Tuple[List[str], List[str]]:
    errors = []
    warnings = []

    # Check BOM (use raw open to detect, then load with BOM stripping)
    has_bom = detect_bom(filepath)
    if has_bom:
        errors.append("File has UTF-8 BOM (should use plain UTF-8)")

    # Validate JSON (strip BOM automatically if present)
    try:
        data = load_json(filepath, strip_bom=has_bom)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e.msg} (line {e.lineno})")
        return errors, warnings
    except Exception as e:
        errors.append(f"Cannot read: {e}")
        return errors, warnings

    # Check it is a dict
    if not isinstance(data, dict):
        errors.append("Root element must be a JSON object")

    # Check required sections
    top_keys = set(data.keys())
    missing = REQUIRED_SECTIONS - top_keys
    if missing:
        errors.append(f"Missing required top-level sections: {', '.join(sorted(missing))}")

    return errors, warnings


def main() -> int:
    if not os.path.isdir(TRANSLATIONS_DIR):
        print(f"ERROR: translations directory not found: {TRANSLATIONS_DIR}", file=sys.stderr)
        return 1

    files = sorted(f for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".json"))
    if not files:
        print("No translation files found.", file=sys.stderr)
        return 1

    # Load reference (en.json)
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    if not os.path.isfile(en_path):
        print("ERROR: en.json not found — cannot check key coverage", file=sys.stderr)
        return 1

    try:
        en_data = load_json(en_path)
    except Exception as e:
        print(f"ERROR: Cannot load en.json: {e}")
        return 1

    en_flat = flatten(en_data)

    total_errors = 0
    total_warnings = 0
    results = []

    for fname in files:
        code = fname[:-5]
        filepath = os.path.join(TRANSLATIONS_DIR, fname)
        errors, warnings = validate_file(filepath)

        # Compare keys against en.json
        if not errors:
            try:
                data = load_json(filepath)
                flat = flatten(data)
                missing_keys = [k for k in en_flat if k not in flat]
                extra_keys = [k for k in flat if k not in en_flat]
                if missing_keys:
                    errors.append(f"Missing {len(missing_keys)} keys present in en.json")
                if extra_keys:
                    warnings.append(f"{len(extra_keys)} extra keys not in en.json")

                # Placeholder check
                for k in en_flat:
                    en_val = str(en_flat[k])
                    if k in flat:
                        lang_val = str(flat[k])
                        en_ph = set(extract_placeholders(en_val))
                        lang_ph = set(extract_placeholders(lang_val))
                        if en_ph != lang_ph:
                            missing_ph = en_ph - lang_ph
                            extra_ph = lang_ph - en_ph
                            parts = []
                            if missing_ph:
                                parts.append(f"missing: {missing_ph}")
                            if extra_ph:
                                parts.append(f"extra: {extra_ph}")
                            warnings.append(f"Key '{k}' placeholder mismatch: {', '.join(parts)}")
            except Exception as e:
                errors.append(f"Key comparison failed: {e}")

        status = "FAIL" if errors else "PASS"
        results.append((code, status, errors, warnings))
        total_errors += len(errors)
        total_warnings += len(warnings)

    # Print report
    print(f"{'='*60}")
    print(f"  Translation Validation Report")
    print(f"{'='*60}")
    print(f"  Files scanned  : {len(files)}")
    print(f"  Passed         : {sum(1 for _, s, _, _ in results if s == 'PASS')}")
    print(f"  Failed         : {sum(1 for _, s, _, _ in results if s == 'FAIL')}")
    print(f"  Total errors   : {total_errors}")
    print(f"  Total warnings : {total_warnings}")
    print(f"{'='*60}")
    print()

    for code, status, errors, warnings in results:
        label = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{label}] {code}.json")
        for e in errors:
            print(f"         ERROR: {e}")
        for w in warnings:
            print(f"         WARN:  {w}")
        print()

    print(f"{'='*60}")
    if total_errors:
        print(f"  !! {total_errors} error(s) - fix before deployment")
    else:
        print(f"  ** All files valid")
    print(f"{'='*60}")

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
