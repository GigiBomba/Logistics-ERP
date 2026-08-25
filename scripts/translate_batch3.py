#!/usr/bin/env python3
"""Translate ALL remaining untranslated English values in sr.json, el.json, sk.json, pl.json.

Uses comprehensive phrase-level dictionaries (500+ entries each)
plus word-level fallback for each target language.

Serbian (sr) → Serbian Cyrillic
Greek (el)  → Greek
Slovak (sk) → Slovak
Polish (pl) → Polish

Usage: python scripts/translate_batch3.py
"""
from __future__ import annotations


import json
import os
import re
import sys

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
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


def unflatten(flat):
    result = {}
    for key, value in sorted(flat.items()):
        parts = key.split(".")
        set_nested(result, parts, value)
    return result


def is_untranslatable(val):
    if not isinstance(val, str) or not val:
        return True
    if re.match(r'^[\d\.,\s%€\$£±\-─—=]+$', val):
        return True
    if val.startswith(('SELECT ', 'SELECT *', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')):
        return True
    if '@' in val and '.' in val:
        return True
    if val.startswith(('data/', '\\\\', '/', '*.', 'Image files')):
        return True
    if re.match(r'^[·.]+$', val):
        return True
    upper = val.upper()
    if upper in {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
                 'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI',
                 'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8', 'MB',
                 'MB.', 'AI', 'R&D', 'HQ', 'POD', 'ADR', 'EORI', 'COD', 'YTD',
                 'DDD', 'TGD', 'ZIP', 'L/100KM', '€/KM', 'INV-'}:
        return True
    if val in ('EUR', 'RON', 'USD', 'GBP'):
        return True
    # Allow VAT to be translated (it's an acronym but commonly translated)
    # Allow IDs and common placeholder-like values to remain untranslated
    return False


def translate_word_by_word(text, word_map):
    """Translate text by replacing individual words using the word map.
    Preserves {} placeholders and other special patterns."""
    if not isinstance(text, str) or not text:
        return None
    # Check if entire phrase is in word_map as key
    if text in word_map:
        return word_map[text]
    # Handle special characters
    words = text.split()
    translated_words = []
    changed = False
    for w in words:
        if "{" in w or "}" in w:
            translated_words.append(w)
            continue
        # Check with punctuation
        clean = w.strip(".,;:!?()[]\"'")
        punct_before = w[:len(w)-len(w.lstrip(".,;:!?()[]\"'"))]
        punct_after = w[len(w.rstrip(".,;:!?()[]\"'")):]
        if clean in word_map:
            t = word_map[clean]
            translated_words.append(punct_before + t + punct_after)
            if w != punct_before + t + punct_after:
                changed = True
        elif clean.capitalize() in word_map:
            t = word_map[clean.capitalize()]
            translated_words.append(punct_before + t + punct_after)
            changed = True
        elif clean.lower() in word_map:
            t = word_map[clean.lower()]
            translated_words.append(punct_before + t + punct_after)
            changed = True
        else:
            translated_words.append(w)
    result = " ".join(translated_words)
    if result == text:
        return None
    return result


# ─── MAIN ───

def translate_all(en_flat, lang_code, word_map):
    """Translate all English values in a language file using word_map."""
    path = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
    lang_data = load_json(path)
    lang_flat = flatten(lang_data)
    changes = 0
    for key, en_val in sorted(en_flat.items()):
        if key not in lang_flat:
            continue
        if not isinstance(en_val, str) or not isinstance(lang_flat[key], str):
            continue
        if en_val == "":
            continue
        lang_val = lang_flat[key]
        if lang_val != en_val:
            continue
        if is_untranslatable(en_val):
            continue
        translated = translate_word_by_word(en_val, word_map)
        if translated is not None and translated != en_val:
            lang_flat[key] = translated
            changes += 1
    nested = unflatten(lang_flat)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nested, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return changes


if __name__ == "__main__":
    # Load en.json reference
    en_data = load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
    en_flat = flatten(en_data)

    print("=" * 60)
    print("  Batch Translation v3 — 4 remaining languages")
    print("=" * 60)

    # Will be populated with dictionaries
# ─── DICTIONARIES ───

# NOTE: Dictionaries are loaded from _dicts.py in the same directory.
# This keeps the main script manageable.

if __name__ == "__main__":
    # Load en.json reference
    en_data = load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
    en_flat = flatten(en_data)

    print("=" * 60)
    print("  Batch Translation v3 — 4 remaining languages")
    print("=" * 60)

    # Import dictionaries from generated module
    sys.path.insert(0, os.path.dirname(__file__))
    try:
        from _dicts import SR_WORDS, EL_WORDS, SK_WORDS, PL_WORDS
        dicts_loaded = True
    except ImportError:
        print("  WARNING: _dicts.py not found. Building inline dictionaries.")
        dicts_loaded = False

    if not dicts_loaded:
        # Inline minimal dictionaries (will be extended by _dicts.py)
        SR_WORDS = {}
        EL_WORDS = {}
        SK_WORDS = {}
        PL_WORDS = {}

    targets = [
        ("sr", SR_WORDS, "Serbian (Cyrillic)"),
        ("el", EL_WORDS, "Greek"),
        ("sk", SK_WORDS, "Slovak"),
        ("pl", PL_WORDS, "Polish"),
    ]

    total_changes = 0
    for code, words, name in targets:
        print(f"\n  Translating {name} ({code}.json)...", end=" ")
        try:
            n = translate_all(en_flat, code, words)
            total_changes += n
            print(f"{n} values translated")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  Total translations made: {total_changes}")
    print(f"{'='*60}")

    # Print coverage
    print("\n  Final coverage:")
    for code, _, name in targets:
        path = os.path.join(TRANSLATIONS_DIR, f"{code}.json")
        try:
            data = load_json(path)
            flat = flatten(data)
            total = len(en_flat)
            untrans = sum(1 for k, v in flat.items() if k in en_flat and isinstance(v, str) and isinstance(en_flat[k], str) and v == en_flat[k] and en_flat[k] != "")
            trans = total - untrans
            pct = 100 * trans / total
            print(f"    {code}.json: {trans}/{total} ({pct:.1f}%)")
        except Exception as e:
            print(f"    {code}.json: ERROR {e}")

    print(f"{'='*60}")


