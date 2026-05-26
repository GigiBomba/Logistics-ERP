#!/usr/bin/env python3
"""Translation validation tool.
Compares every language JSON against ro.json (master template).
Detects missing keys, placeholder mismatches, broken arrays, and nesting issues.

Usage:
    python services/translation_validator.py
    python -m services.translation_validator
"""
import json
import os
import re
import sys
from typing import Dict, List, Tuple

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
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


def validate_language(
    code: str, template_flat: dict, en_flat: dict
) -> Tuple[bool, List[str]]:
    """Validate a single language file. Returns (passed, list_of_errors)."""
    path = os.path.join(TRANSLATIONS_DIR, f"{code}.json")
    errors = []

    if not os.path.isfile(path):
        return False, [f"File not found: {path}"]

    try:
        data = load_json(path)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    flat = flatten(data)

    # 1. Missing keys
    for k in template_flat:
        if k not in flat:
            errors.append(f"MISSING: {k}")

    # 2. Extra keys (allow only language_name)
    for k in flat:
        if k not in template_flat and k != "language_name":
            errors.append(f"EXTRA: {k}")

    # 3. Placeholder mismatch
    for k in template_flat:
        v_tmpl = template_flat[k]
        v_lang = flat.get(k)
        if isinstance(v_tmpl, str) and isinstance(v_lang, str):
            tmpl_ph = extract_placeholders(v_tmpl)
            lang_ph = extract_placeholders(v_lang)
            if tmpl_ph != lang_ph:
                errors.append(
                    f"PLACEHOLDER: {k}\n"
                    f"    RO: {v_tmpl[:60]}\n"
                    f"    {code}: {v_lang[:60]}"
                )

    # 4. Array vs non-array mismatch
    for k in template_flat:
        if isinstance(template_flat[k], list) and not isinstance(flat.get(k), list):
            errors.append(f"ARRAY: {k} should be a list")
        if not isinstance(template_flat[k], list) and k in flat and isinstance(flat[k], list):
            errors.append(f"ARRAY: {k} should NOT be a list")

    # 5. Section structure mismatch (skip language_name, which is intentionally a leaf key)
    for section in template_flat:
        if section.count(".") == 0 and section not in ("language_name",) and section in flat:
            if isinstance(flat[section], str):
                errors.append(f"STRUCTURE: {section} should be an object, got string")

    # 6. Check for null/empty string values where template has content
    for k in template_flat:
        v_lang = flat.get(k)
        if v_lang is None:
            errors.append(f"NULL: {k} is null")
        if isinstance(v_lang, str) and v_lang.strip() == "" and isinstance(template_flat[k], str) and template_flat[k].strip():
            errors.append(f"EMPTY: {k} is empty string")

    return len(errors) == 0, errors


def main():
    tmpl_path = os.path.join(TRANSLATIONS_DIR, "ro.json")
    if not os.path.isfile(tmpl_path):
        print(f"ERROR: Master template ro.json not found at {tmpl_path}")
        sys.exit(1)

    template = load_json(tmpl_path)
    en = load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
    template_flat = flatten(template)
    en_flat = flatten(en)

    LANGUAGES = [
        "en", "fr", "de", "es", "ro",
        "ru", "it", "pl", "uk", "nl",
        "sr", "hr", "tr", "pt", "hu",
        "cs", "sk", "bs", "sl", "sv",
        "el", "bg",
    ]

    print(f"{'Language':>6s}  {'Keys':>4s}  {'Trans':>4s}  {'Pct':>5s}  Status")
    print("-" * 55)

    all_pass = True
    for code in LANGUAGES:
        passed, errors = validate_language(code, template_flat, en_flat)
        path = os.path.join(TRANSLATIONS_DIR, f"{code}.json")
        if os.path.isfile(path):
            data = load_json(path)
            flat = flatten(data)
            total = len(flat)
            translated = sum(
                1 for k in flat if k in en_flat and flat[k] != en_flat[k]
            )
            pct = translated / max(total, 1) * 100
            status = "PASS" if passed else f"FAIL ({len(errors)} issues)"
            print(f"{code:>6s}  {total:4d}  {translated:4d}  {pct:4.0f}%  {status}")
            if not passed:
                all_pass = False
                for e in errors:
                    for line in e.split("\n"):
                        print(f"         {line}")
        else:
            print(f"{code:>6s}  {'MISSING':>15s}")

    print()
    if all_pass:
        print("All languages validated successfully.")
    else:
        print("Some languages have issues (see above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
