#!/usr/bin/env python3
"""Deep-merge all missing keys from en.json into every translation file.

For each language:
  1. Read en.json (reference) and the language file
  2. Recursively add any missing sections/keys from en.json
  3. Keep existing translated values
  4. Write back preserving structure
"""

import json
import os
import sys
from copy import deepcopy

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")


def deep_merge(base: dict, overlay: dict) -> dict:
    """Merge `overlay` into `base` recursively.
    
    - For each key in `base`:
      - If key is missing from overlay, use base value (English fallback)
      - If key exists in both and both are dicts, recurse
      - If key exists in overlay and is not a dict, keep overlay value
    - For each key in overlay that is NOT in base, it's an extra key — keep it
      (validation will report it as a warning, but we preserve extra keys)
    """
    result = deepcopy(base)
    for k, v in overlay.items():
        if k in result:
            if isinstance(result[k], dict) and isinstance(v, dict):
                result[k] = deep_merge(result[k], v)
            else:
                # Keep the translated value
                result[k] = deepcopy(v)
        else:
            # Extra key not in en.json — preserve it
            result[k] = deepcopy(v)
    return result


def fix_ro_json(data: dict) -> dict:
    """Fix ro.json: the 'main' section keys are merged into 'nav'.
    
    Move nav.main.* keys to main.* and ensure main section exists.
    """
    nav = data.get("nav", {})
    main_keys_from_nav = {
        "section_identify", "truck_label", "client_label", "section_finance",
        "offer_price", "currency_label", "currencies", "section_costs",
        "salary_label", "extra_costs_label", "section_planning",
        "start_date_label", "duration_label", "payment_term_label",
        "calculate_button", "placeholder_info", "net_profit", "gross_rate",
        "margin", "separator", "cost_breakdown", "warning_title",
        "fields_required", "save_success", "error_title", "check_data",
        "fuel_updated_at", "fuel_age", "fuel_offline", "vat_checkbox",
        "offer_price_pre_vat", "offer_price_post_vat", "results_header",
        "empty_calc_title", "empty_calc_subtitle", "result_revenue",
        "result_cost", "result_profit", "result_rate", "result_margin",
    }
    main_section = {}
    for key in list(nav.keys()):
        if key in main_keys_from_nav:
            main_section[key] = nav.pop(key)
    if main_section:
        data.setdefault("main", {})
        data["main"].update(main_section)
    return data


def fix_language(data: dict, lang_code: str) -> dict:
    """Apply language-specific structural fixes."""
    if lang_code == "ro":
        data = fix_ro_json(data)
    return data


def main():
    en_path = os.path.join(TRANSLATIONS_DIR, "en.json")
    if not os.path.isfile(en_path):
        print(f"ERROR: en.json not found at {en_path}")
        return 1

    with open(en_path, encoding="utf-8-sig") as f:
        en_data = json.load(f)

    files = sorted(f for f in os.listdir(TRANSLATIONS_DIR) if f.endswith(".json"))
    processed = 0
    skipped = 0

    for fname in files:
        if fname == "en.json":
            continue
        
        lang_code = fname[:-5]
        filepath = os.path.join(TRANSLATIONS_DIR, fname)
        
        with open(filepath, encoding="utf-8-sig") as f:
            lang_data = json.load(f)
        
        # Apply structural fixes first
        lang_data = fix_language(lang_data, lang_code)
        
        # Deep-merge en.json into language data
        merged = deep_merge(en_data, lang_data)
        
        # Write back
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
            f.write("\n")
        
        print(f"  OK {fname}: merged (kept existing translations)")
        processed += 1

    print(f"\nDone. Processed {processed} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
