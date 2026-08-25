#!/usr/bin/env python3
"""Translate ALL remaining English-matching values in cs.json, pt.json, hu.json, tr.json.

Uses comprehensive phrase-level + word-level dictionaries (500+ entries each)
built from already-translated entries and domain knowledge.

Usage: python scripts/translate_batch2.py
"""
from __future__ import annotations


import json
import os
import re
import sys
from copy import deepcopy

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

# ─── ACRONYMS / DO NOT TRANSLATE ───
ACRONYMS = {
    "ID", "KM", "VIN", "EUR", "N/A", "CSV", "PDF", "OCR", "GPS",
    "API", "CMR", "KPI", "SMTP", "DSO", "SLA", "SOC", "GDPR", "CUI",
    "VAT", "ETA", "SMS", "GBP", "USD", "RON", "JSON", "BOM", "UTF-8",
    "MB", "MB.", "AI", "R&D", "HQ", "POD", "ADR", "EORI", "COD", "YTD",
    "DDD", "TGD", "ZIP", "L/100KM", "EUR/KM",
}

UPPER_ACRONYMS = {a.upper() for a in ACRONYMS}
KEEP_AS_ENGLISH = {
    "EUR", "RON", "GBP", "USD", "VIN", "KM", "PDF", "CSV", "JSON",
    "N/A", "OCR", "GPS", "API", "CMR", "KPI", "SMTP",
    "e.g.", "i.e.",
    # Firm names / loanwords that should stay as-is in translations
    "ERP",
    "Excel",
    "OK",
    "Mihai Popescu",
    "John Smith",
    "CEO, Smith Logistics",
}

TARGET_LANGS = ["cs", "pt", "hu", "tr"]


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def flatten(d, prefix=""):
    """Flatten nested dict, preserving lists as-is (don't recurse into lists)."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            items[key] = v  # Keep lists as-is
        else:
            items[key] = v
    return items


def set_nested(d, key_parts, value):
    """Set a nested value, handling lists properly."""
    cur = d
    for p in key_parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[key_parts[-1]] = value


def unflatten(flat):
    """Reconstruct nested dict from flat keys, preserving list values."""
    result = {}
    for key, value in sorted(flat.items()):
        parts = key.split(".")
        set_nested(result, parts, value)
    return result


# Common international words that stay the same in most languages
LOANWORDS = {
    "ERP", "EMAIL", "ROLE", "PASSWORD", "STATUS", "INFO", "OK",
    "FINANCE", "EMAIL", "ROLE", "STATUS", "EXCEL", "LOGO",
    "PROFORMA", "PROFORMAS", "BRANDING", "MODEL", "PLATFORM",
    "TOKEN", "HOST", "SCORE", "RECORDS", "RESET", "FILTER",
    "SORT", "EXPORT", "IMPORT", "PRINT", "PREVIEW", "PROFILE",
    "DASHBOARD", "ANALYTICS", "CALENDAR", "DIGITAL", "STANDARD",
    "PREMIUM", "BASIC", "PARTNER", "BONUS", "TOP", "NET",
}

# Names and brands that should stay as-is
NAMES_AND_BRANDS = {
    "Mihai Popescu", "John Smith", "Sarah M\u00fcller",
    "CEO, Smith Logistics",
    "Google Maps", "GraphHopper", "Operion", "Operion ERP",
    "PaddleOCR", "Redis", "Celery",
}


def is_untranslatable(val):
    """Return True if val should NOT be translated."""
    if not isinstance(val, str) or not val:
        return True
    if re.match(r'^[\d\.,\s%\u20ac$\u00a3\u00b1\-—=\'\"\u2032\u2033]+$', val):
        return True
    if val.startswith(('SELECT ', 'SELECT *', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')):
        return True
    if '@' in val and '.' in val:
        return True
    if val.startswith(('data/', '\\\\', '/', '*.', 'Image files')):
        return True
    if val in KEEP_AS_ENGLISH:
        return True
    if val.upper() in UPPER_ACRONYMS:
        return True
    # Check if value matches a known acronym with some punctuation
    clean = re.sub(r'[\(\)\.:\s]', '', val)
    if clean.upper() in UPPER_ACRONYMS:
        return True
    if re.match(r'^\{[^}]*\}$', val):
        return True
    # Check if it's a common loanword or name
    if val in LOANWORDS:
        return True
    if val in NAMES_AND_BRANDS:
        return True
    # Check for person names (first+last capitalized)
    if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+$', val) and val not in {"About Operion", "Our Story", "Our Values", "Our Team", "Our Mission", "Customer First", "Start Free Trial", "Talk to Sales", "See How It Works", "Sign In", "Sign Out", "Sign up", "Full Name", "Company Name", "Welcome back", "Back to home", "Create Account", "Create account", "Forgot password", "Hide password", "Show password", "Account created", "Failed to create", "Signed in successfully", "Failed to sign", "Please enter", "Confirm Password", "Repeat your", "Already have", "Don't have", "Start your", "Creating account", "Name must be", "Password must", "Passwords don't"}:
        return True
    return False


def check_untranslatable_value(val):
    """Check if a target value should stay as-is (acronym match etc)."""
    if not isinstance(val, str) or not val:
        return True
    if val.upper() in UPPER_ACRONYMS:
        return True
    return False


def build_value_map(data, en_flat):
    """Build a map of English -> translated from already-translated entries."""
    flat = flatten(data)
    vmap = {}
    for k, en_v in en_flat.items():
        if k in flat:
            v = flat[k]
            if isinstance(v, str) and isinstance(en_v, str) and v.strip() and en_v.strip():
                if v != en_v and not is_untranslatable(en_v):
                    vmap[en_v] = v
    return vmap


def word_level_fallback(english_text, word_dict):
    """Translate a phrase using word-by-word lookup.
    Returns translated text or None if not translatable.
    """
    # Try exact match first
    if english_text in word_dict:
        return word_dict[english_text]

    # Try preserving placeholders while translating around them
    parts = re.split(r'(\{[^}]*\})', english_text)
    translated_parts = []
    for part in parts:
        if re.match(r'^\{[^}]*\}$', part):
            translated_parts.append(part)
        elif part.strip():
            # Try whole phrase in dict
            if part.strip() in word_dict:
                translated_parts.append(word_dict[part.strip()])
            else:
                # Word by word
                words = part.split()
                twords = []
                for w in words:
                    # Check with punctuation
                    clean_w = w.strip('.,:;!?()[]\'"')
                    punct_before = w[:len(w)-len(clean_w)]
                    punct_after = w[len(clean_w):]
                    if clean_w in word_dict:
                        twords.append(punct_before + word_dict[clean_w] + punct_after)
                    elif clean_w.lower() in {w.lower() for w in word_dict}:
                        # Try case-insensitive match
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


def analyze_coverage(lang_code):
    """Return (total, translated, pct) for a language file."""
    en = load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
    en_flat = flatten(en)
    data = load_json(os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json"))
    flat = flatten(data)
    
    total = 0
    translated_count = 0
    for k in en_flat:
        en_v = en_flat[k]
        if isinstance(en_v, str) and en_v.strip():
            total += 1
            if k in flat:
                v = flat[k]
                if isinstance(v, str) and v != en_v:
                    translated_count += 1
                elif isinstance(v, str) and is_untranslatable(v):
                    translated_count += 1
    
    pct = (translated_count / total * 100) if total else 0
    return total, translated_count, pct

# ─── DICTIONARIES ──────────────────────────────────────────
# These are imported from separate JSON files for manageability

def load_dictionaries(lang_code):
    """Load phrase and word dictionaries for a language."""
    phrases_path = os.path.join(TRANSLATIONS_DIR, f"_dict_{lang_code}_phrases.json")
    words_path = os.path.join(TRANSLATIONS_DIR, f"_dict_{lang_code}_words.json")
    
    phrases = {}
    words = {}
    
    if os.path.exists(phrases_path):
        with open(phrases_path, "r", encoding="utf-8-sig") as f:
            phrases = json.load(f)
    
    if os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8-sig") as f:
            words = json.load(f)
    
    return phrases, words


def translate_value(en_val, phrases, words, vmap, lang_code):
    """Translate a single English value using multiple strategies."""
    if is_untranslatable(en_val):
        return None
    
    # Strategy 1: Already known from value map
    if en_val in vmap:
        return vmap[en_val]
    
    # Strategy 2: Exact phrase match
    if en_val in phrases:
        return phrases[en_val]
    
    # Strategy 3: Word-level fallback
    result = word_level_fallback(en_val, words)
    if result:
        return result
    
    # Strategy 4: Check partial matches in phrases
    # (for values with placeholders)
    for phrase_en, phrase_trans in phrases.items():
        # Try to match by replacing placeholders with wildcards
        phrase_pattern = re.escape(phrase_en).replace(r'\{', '{').replace(r'\}', '}')
        # Keep placeholders as regex capture groups
        phrase_pattern = re.sub(r'\{[^}]*\}', '(.+)', phrase_pattern)
        try:
            m = re.match(f'^{phrase_pattern}$', en_val)
            if m:
                # Reconstruct with translated pattern
                result = phrase_trans
                for group in m.groups():
                    # Try to translate the captured group too
                    translated_group = translate_value(group, phrases, words, vmap, lang_code)
                    if translated_group:
                        result = result.replace('(.+)', translated_group, 1)
                    else:
                        result = result.replace('(.+)', group, 1)
                result = result.replace('(.+)', '{}')  # Clean up any remaining
                return result
        except re.error:
            continue
    
    return None


def translate_file(lang_code, phrases, words):
    """Translate all English values in a language file."""
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    target_path = os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json")
    
    en_data = load_json(en_path)
    target_data = load_json(target_path)
    
    en_flat = flatten(en_data)
    target_flat = flatten(target_data)
    
    # Build value map from already-translated entries
    vmap = build_value_map(target_data, en_flat)
    
    # Also add the phrase dict entries to vmap
    for k, v in phrases.items():
        if k not in vmap:
            vmap[k] = v
    
    stats = {"total": 0, "translated": 0, "already": 0, "skipped": 0, "untranslatable": 0}
    
    for k, en_v in en_flat.items():
        if not isinstance(en_v, str) or not en_v.strip():
            continue
        stats["total"] += 1
        
        if k not in target_flat:
            stats["skipped"] += 1
            continue
        
        current_v = target_flat[k]
        if not isinstance(current_v, str):
            continue
        
        # Already translated (or untranslatable value)
        if current_v != en_v:
            stats["already"] += 1
            continue
        
        if is_untranslatable(en_v):
            stats["untranslatable"] += 1
            continue
        
        # Try to translate
        translation = translate_value(en_v, phrases, words, vmap, lang_code)
        if translation and translation != en_v:
            target_flat[k] = translation
            stats["translated"] += 1
        else:
            stats["skipped"] += 1
    
    # Write back
    new_data = unflatten(target_flat)
    save_json(target_path, new_data)
    
    return stats


def main():
    print("=" * 60)
    print("  Translation Batch 2 - Czech, Portuguese, Hungarian, Turkish")
    print("=" * 60)
    
    total_before = {}
    for lang in TARGET_LANGS:
        _, t, p = analyze_coverage(lang)
        total_before[lang] = (t, p)
        print(f"  {lang}.json: {p:.1f}% ({t} translated)")
    
    print()
    
    all_stats = {}
    for lang in TARGET_LANGS:
        print(f"  Processing {lang}.json...")
        phrases, words = load_dictionaries(lang)
        print(f"    Loaded {len(phrases)} phrases, {len(words)} words")
        stats = translate_file(lang, phrases, words)
        all_stats[lang] = stats
        print(f"    Total: {stats['total']}, Already: {stats['already']}, "
              f"New: {stats['translated']}, Skipped: {stats['skipped']}, "
              f"Untranslatable: {stats['untranslatable']}")
    
    print()
    print("=" * 60)
    print("  Results")
    print("=" * 60)
    for lang in TARGET_LANGS:
        total, translated, pct = analyze_coverage(lang)
        before_pct = total_before[lang][1]
        print(f"  {lang}.json: {before_pct:.1f}% -> {pct:.1f}% ({translated}/{total})")
    
    print()
    print("  Done.")


if __name__ == "__main__":
    main()
