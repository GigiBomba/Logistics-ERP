#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Translate ALL remaining languages below 80% coverage (13 languages).

Targets: bs, hr, sv, sl, sr, el, ru, sk, pl, uk, es, fr, de.

Strategy: Cross-language learning from high-coverage languages.
  For each target language, borrow translations from the closest
  high-coverage language(s), plus word-level fallback.

Usage: python scripts/translate_remaining.py
"""

import json
import os
import re
import sys

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")
TARGET_LANGS = ["bs", "hr", "sv", "sl", "sr", "el", "ru", "sk", "pl", "uk", "es", "fr", "de"]
HIGH_COVERAGE = ["cs", "pt", "hu", "tr", "nl", "ro", "it", "bg"]
ALL_LANGS = TARGET_LANGS + HIGH_COVERAGE

ACRONYMS = {
    "ID", "KM", "VIN", "EUR", "N/A", "CSV", "PDF", "OCR", "GPS",
    "API", "CMR", "KPI", "SMTP", "DSO", "SLA", "SOC", "GDPR", "CUI",
    "VAT", "ETA", "SMS", "GBP", "USD", "RON", "JSON", "BOM", "UTF-8",
    "MB", "MB.", "AI", "R&D", "HQ", "POD", "ADR", "EORI", "COD", "YTD",
    "DDD", "TGD", "ZIP", "L/100KM", "EUR/KM", "\u20ac/KM", "L/100km",
    "HTML", "XML", "INV-", "LKW", "CASHFLOW", "OPERION", "GRAPHOPPER", "PADDLEOCR",
}
UPPER_ACRONYMS = {a.upper() for a in ACRONYMS}
KEEP_AS_ENGLISH = {
    "EUR", "RON", "GBP", "USD", "VIN", "KM", "PDF", "CSV", "JSON",
    "N/A", "OCR", "GPS", "API", "CMR", "KPI", "SMTP",
    "e.g.", "i.e.", "ERP", "Excel", "OK",
    "Mihai Popescu", "John Smith", "CEO, Smith Logistics", "Sarah M\u00fcller",
}
LOANWORDS = {
    "ERP", "EMAIL", "ROLE", "PASSWORD", "STATUS", "INFO", "OK",
    "FINANCE", "EXCEL", "LOGO", "PROFORMA", "PROFORMAS", "BRANDING",
    "MODEL", "PLATFORM", "TOKEN", "HOST", "SCORE", "RECORDS", "RESET",
    "FILTER", "SORT", "EXPORT", "IMPORT", "PRINT", "PREVIEW", "PROFILE",
    "DASHBOARD", "ANALYTICS", "CALENDAR", "DIGITAL", "STANDARD",
    "PREMIUM", "BASIC", "PARTNER", "BONUS", "TOP", "NET",
}
NAMES_AND_BRANDS = {
    "Mihai Popescu", "John Smith", "Sarah M\u00fcller", "CEO, Smith Logistics",
    "Google Maps", "GraphHopper", "Operion", "Operion ERP",
    "PaddleOCR", "Redis", "Celery",
}
COMMON_ENGLISH_PHRASES = {
    "About Operion", "Our Story", "Our Values", "Our Team", "Our Mission",
    "Customer First", "Start Free Trial", "Talk to Sales", "See How It Works",
    "Sign In", "Sign Out", "Sign up", "Full Name", "Company Name",
    "Welcome back", "Back to home", "Create Account", "Create account",
    "Forgot password", "Hide password", "Show password", "Account created",
    "Failed to create", "Signed in successfully", "Failed to sign",
    "Please enter", "Confirm Password", "Repeat your", "Already have",
    "Don't have", "Start your", "Creating account", "Name must be",
    "Password must", "Passwords don't", "Operion ERP",
}


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def _flat(d, p=""):
    """Flatten to strings (matching _all_coverage.py)."""
    items = {}
    for k, v in d.items():
        key = f"{p}.{k}" if p else k
        if isinstance(v, dict):
            items.update(_flat(v, key))
        else:
            items[key] = str(v)
    return items

def flatten(d, prefix=""):
    """Flatten preserving list types."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            items[key] = v
        else:
            items[key] = v
    return items

def set_nested(d, key_parts, value):
    cur = d
    for p in key_parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[key_parts[-1]] = value

def unflatten(flat_items):
    result = {}
    for key, value in sorted(flat_items.items()):
        parts = key.split(".")
        set_nested(result, parts, value)
    return result

def is_untranslatable(val):
    if not isinstance(val, str) or not val:
        return True
    if re.match(r'^[\\d\\.,\\s%\\u20ac\$\\u00a3\\u00b1\\-—=\\'\"\\u2032\\u2033]+\$', val):
        return True
    if val.startswith(('SELECT ', 'SELECT *', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')):
        return True
    if '@' in val and '.' in val:
        return True
    if val.startswith(('data/', '\\\\\\\\', '/', '*.', 'Image files')):
        return True
    if val in KEEP_AS_ENGLISH:
        return True
    if val.upper() in UPPER_ACRONYMS:
        return True
    clean = re.sub(r'[\\(\\)\\.:\\s]', '', val)
    if clean.upper() in UPPER_ACRONYMS:
        return True
    if re.match(r'^\\{[^}]*\\}\$', val):
        return True
    if val in LOANWORDS:
        return True
    if val in NAMES_AND_BRANDS:
        return True
    if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+\$', val) and val not in COMMON_ENGLISH_PHRASES:
        return True
    return False

def build_value_map(lang_data, en_flat):
    """Build EN->TL map from already-translated entries."""
    flat = flatten(lang_data)
    vmap = {}
    for k, en_v in en_flat.items():
        if k in flat:
            v = flat[k]
            if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                if v != en_v and not is_untranslatable(en_v):
                    vmap[en_v] = v.strip()
    return vmap

def load_all_donors():
    """Load EN->TL maps from all high-coverage languages."""
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    en_data = load_json(en_path)
    en_flat = _flat(en_data)
    donors = {}
    for lang in ALL_LANGS:
        path = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")
        if os.path.exists(path):
            data = load_json(path)
            donors[lang] = {
                "data": data,
                "flat": flatten(data),
                "vmap": build_value_map(data, en_flat),
            }
    return en_data, en_flat, donors

# Language family mapping for cross-language borrowing
# For each target, list donor languages in order of priority
# High-coverage donors (>=77%) are preferred
DONOR_PRIORITY = {
    "bs": ["hr", "cs", "sr", "bg", "pl"],  # South Slavic
    "hr": ["cs", "bs", "sr", "bg", "pl"],  # South Slavic
    "sr": ["hr", "cs", "bs", "bg", "ru"],  # South Slavic (Cyrillic)
    "sl": ["cs", "hr", "sk", "pl", "bg"],  # South Slavic
    "sk": ["cs", "pl", "sl", "bg", "hr"],  # West Slavic
    "pl": ["cs", "sk", "sl", "bg", "hr"],  # West Slavic
    "ru": ["uk", "bg", "cs", "pl", "sk"],  # East Slavic
    "uk": ["ru", "bg", "cs", "pl", "sk"],  # East Slavic
    "sv": ["de", "nl", "cs", "pt", "it"],  # Germanic
    "de": ["nl", "sv", "cs", "pt", "it"],  # Germanic
    "el": ["cs", "pt", "it", "hu", "ro"],  # Isolate - try several
    "es": ["pt", "it", "ro", "fr", "nl"],  # Romance
    "fr": ["pt", "it", "ro", "es", "nl"],  # Romance
}

def word_level_fallback(english_text, word_dict):
    """Translate phrase by phrase, then word by word."""
    if english_text in word_dict:
        return word_dict[english_text]
    parts = re.split(r'(\\{[^}]*\\})', english_text)
    translated_parts = []
    for part in parts:
        if re.match(r'^\\{[^}]*\\}\$', part):
            translated_parts.append(part)
        elif part.strip():
            if part.strip() in word_dict:
                translated_parts.append(word_dict[part.strip()])
            else:
                words = part.split()
                twords = []
                for w in words:
                    clean_w = w.strip('.,:;!?()[]\\'\"')
                    punct_before = w[:len(w)-len(clean_w)]
                    punct_after = w[len(clean_w):]
                    if clean_w in word_dict:
                        twords.append(punct_before + word_dict[clean_w] + punct_after)
                    elif clean_w.lower() in {wd.lower() for wd in word_dict}:
                        for dk, dv in word_dict.items():
                            if dk.lower() == clean_w.lower():
                                twords.append(punct_before + dv + punct_after)
                                break
                        else:
                            twords.append(w)
                    else:
                        twords.append(w)
                translated_parts.append(" ".join(twords))
        else:
            translated_parts.append(part)
    result = "".join(translated_parts)
    return result if result != english_text else None

def translate_file(lang_code, en_flat, en_data, donors):
    """Translate a single language file using cross-language learning."""
    path = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
    target_data = load_json(path)
    target_flat = flatten(target_data)

    # Build value map from this language's own existing translations
    own_vmap = build_value_map(target_data, en_flat)

    # Get the donor language(s) for this target
    donor_priority = DONOR_PRIORITY.get(lang_code, ["cs", "pt", "hu", "tr"])

    # Build combined vmap: own first, then donors
    combined_vmap = dict(own_vmap)

    for donor_lang in donor_priority:
        if donor_lang in donors and donor_lang != lang_code:
            donor_vmap = donors[donor_lang]["vmap"]
            for k, v in donor_vmap.items():
                if k not in combined_vmap and k in en_flat:
                    combined_vmap[k] = v

    # Also add word-level dict from own content
    word_dict = {}
    for k, en_v in en_flat.items():
        if k in target_flat:
            v = target_flat[k]
            if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                if v != en_v and not is_untranslatable(en_v):
                    en_clean = en_v.strip()
                    if len(en_clean.split()) == 1 and ':' not in en_clean:
                        word_dict[en_clean] = v.strip()

    # Add words from donors too
    for donor_lang in donor_priority:
        if donor_lang in donors and donor_lang != lang_code:
            for k, en_v in en_flat.items():
                donor_flat = donors[donor_lang]["flat"]
                if k in donor_flat:
                    v = donor_flat[k]
                    if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                        if v != en_v and not is_untranslatable(en_v):
                            en_clean = en_v.strip()
                            if len(en_clean.split()) == 1 and ':' not in en_clean and en_clean not in word_dict:
                                word_dict[en_clean] = v.strip()

    stats = {"total": 0, "translated": 0, "already": 0, "skipped": 0, "untranslatable": 0}

    for k, en_v in en_flat.items():
        en_v_str = str(en_v).strip() if not isinstance(en_v, str) else en_v.strip()
        if not en_v_str:
            continue
        stats["total"] += 1
        if k not in target_flat:
            stats["skipped"] += 1
            continue
        current_v = target_flat[k]
        if not isinstance(current_v, str):
            continue
        cur_v_str = current_v.strip()
        if cur_v_str != en_v_str:
            stats["already"] += 1
            continue
        if is_untranslatable(en_v_str):
            stats["untranslatable"] += 1
            continue

        # Try own vmap first
        translation = combined_vmap.get(en_v_str)
        if translation and translation != en_v_str:
            target_flat[k] = translation
            stats["translated"] += 1
            continue

        # Word-level fallback
        translation = word_level_fallback(en_v_str, word_dict)
        if translation and translation != en_v_str:
            target_flat[k] = translation
            stats["translated"] += 1
            continue

        stats["skipped"] += 1

    new_data = unflatten(target_flat)
    save_json(path, new_data)
    return stats

