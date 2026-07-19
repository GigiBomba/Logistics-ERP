#!/usr/bin/env python3
"""Translate all English placeholder values in data/translations/el.json to Greek."""
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
EN_PATH = os.path.join(BASE, "data", "translations", "en.json")
EL_PATH = os.path.join(BASE, "data", "translations", "el.json")
TR_PATH = os.path.join(BASE, "data", "translations", "_el_translations.json")

sys.stdout.reconfigure(encoding="utf-8")

ACRONYMS = {
    "ID", "KM", "VIN", "EUR", "N/A", "CSV", "PDF", "OCR", "GPS", "API",
    "CMR", "KPI", "SMTP", "DSO", "SLA", "SOC", "GDPR", "CUI", "VAT",
    "ETA", "SMS", "GBP", "USD", "RON", "JSON", "BOM", "UTF-8", "POD",
    "EORI", "COD", "ADR", "DDD", "TGD", "ZIP", "MB", "AI", "RD",
}

def apply_translations(en_obj, el_obj, translations):
    """Recursively compare, translate matching string values."""
    count = 0
    skipped = []
    keys = set(list(en_obj.keys()) + list(el_obj.keys()))
    for key in keys:
        if key not in en_obj or key not in el_obj:
            continue
        en_val = en_obj[key]
        el_val = el_obj[key]

        if isinstance(en_val, dict) and isinstance(el_val, dict):
            c, s = apply_translations(en_val, el_val, translations)
            count += c
            skipped.extend(s)
        elif isinstance(en_val, list) and isinstance(el_val, list):
            for i in range(min(len(en_val), len(el_val))):
                if isinstance(en_val[i], str) and isinstance(el_val[i], str):
                    if en_val[i] == el_val[i]:
                        en_str = en_val[i].strip()
                        if en_str and en_str.rstrip(".:") not in ACRONYMS and not en_str.startswith("{"):
                            if en_str in translations:
                                el_val[i] = translations[en_str]
                                count += 1
                            else:
                                skipped.append(f"  {key}[{i}]: {en_str[:80]}")
        elif isinstance(en_val, str) and isinstance(el_val, str):
            if en_val == el_val:
                en_str = en_val.strip()
                if en_str and en_str.rstrip(".:") not in ACRONYMS and not en_str.startswith("{"):
                    if en_str in translations:
                        el_obj[key] = translations[en_str]
                        count += 1
                    else:
                        skipped.append(f"  {key}: {en_str[:80]}")
    return count, skipped

# Load files
with open(EN_PATH, "r", encoding="utf-8") as f:
    en_data = json.load(f)
with open(EL_PATH, "r", encoding="utf-8") as f:
    el_data = json.load(f)
with open(TR_PATH, "r", encoding="utf-8") as f:
    TRANSLATIONS = json.load(f)

print(f"Loaded {len(TRANSLATIONS)} translations")

count, skipped = apply_translations(en_data, el_data, TRANSLATIONS)

print(f"\nTranslated: {count}")
print(f"Skipped (no translation found): {len(skipped)}")
if skipped:
    with open(os.path.join(BASE, "data", "translations", "_missing.json"), "w", encoding="utf-8") as f:
        json.dump(skipped, f, ensure_ascii=False, indent=2)
    print(f"Missing list written to _missing.json")

# Write back
with open(EL_PATH, "w", encoding="utf-8") as f:
    json.dump(el_data, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"\nWritten to {EL_PATH}")
