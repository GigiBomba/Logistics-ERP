#!/usr/bin/env python3
"""Fix remaining placeholder mismatches by aligning en.json with translations."""

import json
import os

TRANSLATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

with open(os.path.join(TRANSLATIONS_DIR, "en.json"), encoding="utf-8-sig") as f:
    en = json.load(f)

# Keys where en.json needs to add {} or named placeholders that translations have
# Format: dot.key -> new_value_with_placeholder
fixes = {
    # Fleet error/message keys: translations use {} for format args
    "fleet.search_not_found": "No trucks found: {}",
    "fleet.truck_detail_title": "Truck {}",
    "fleet.error_delete": "Could not delete truck: {}",
    "fleet.error_load": "Could not load trucks: {}",
    "fleet.error_save": "Could not save truck: {}",
    "fleet.error_save_expense": "Could not save expense: {}",
    "fleet.export_csv_error": "CSV export failed: {}",
    "fleet.export_csv_success": "CSV exported: {}",
    "fleet.export_excel_error": "Excel export failed: {}",
    "fleet.export_excel_success": "Excel exported: {}",
    "fleet.export_pdf_error": "PDF export failed: {}",
    "fleet.export_pdf_success": "PDF exported: {}",
    
    # Dispatch board: translations have proper placeholders
    "dispatch_board.available_from": "Available from {next_slot}",
    "dispatch_board.confirm_backward": "Confirm moving trip #{trip_id} back from {old_status} to {new_status}?",
    "dispatch_board.delay_alert_message": "Trip #{trip_id} ({client}) is delayed by over {hours} hours.",
    "dispatch_board.delay_alert_title": "Delay Alert - Trip #{trip_id}",
    "dispatch_board.hours_overdue": "{hours}h overdue",
    "dispatch_board.minutes_overdue": "{minutes}m overdue",
    "dispatch_board.transition_error": "Error moving from {old_status} to {new_status}",
    "dispatch_board.transition_success": "Moved to {new_status}",
    "dispatch_board.unavailable_overlap": "Unavailable: overlaps with trip {trip_ref}",
    
    # Dutch: edit_trip.title uses {number} instead of {}
    # Keep en.json with {} - fix nl.json instead
    
    # Fuel
    "fuel.updated_tooltip": "Fuel prices updated {minutes} ago",
    
    # Maintenance
    "maint.schedule_next_due_km": "Next due at {km} km",
    "maint.status_remaining": "{km} km remaining",
    
    # Route
    "route.stop_n": "Stop {n}",
}

def set_nested(d, key, value):
    parts = key.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value

for key, value in fixes.items():
    set_nested(en, key, value)
    print(f"  Fixed en.json: {key}")

with open(os.path.join(TRANSLATIONS_DIR, "en.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(en, f, indent=2, ensure_ascii=False)
    f.write("\n")

# Fix nl.json edit_trip.title (uses {number} instead of {})
nl_path = os.path.join(TRANSLATIONS_DIR, "nl.json")
with open(nl_path, encoding="utf-8-sig") as f:
    nl = json.load(f)
if "edit_trip" in nl and "title" in nl["edit_trip"]:
    old = nl["edit_trip"]["title"]
    nl["edit_trip"]["title"] = old.replace("{number}", "{}")
    print(f"  Fixed nl.json edit_trip.title: {old} -> {nl['edit_trip']['title']}")
with open(nl_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(nl, f, indent=2, ensure_ascii=False)
    f.write("\n")

# Fix sk.json and uk.json invoice.field_{key}: {Key} vs {key} case mismatch
for lang in ["sk.json", "uk.json"]:
    path = os.path.join(TRANSLATIONS_DIR, lang)
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    if "invoice" in data and "field_{key}" in data["invoice"]:
        old = data["invoice"]["field_{key}"]
        data["invoice"]["field_{key}"] = old.replace("{key}", "{Key}")
        print(f"  Fixed {lang} invoice.field_{{key}}: {old} -> {data['invoice']['field_{key}']}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

# Fix uk.json route.stop_n (extra {n} placeholder)
uk_path = os.path.join(TRANSLATIONS_DIR, "uk.json")
with open(uk_path, encoding="utf-8-sig") as f:
    uk = json.load(f)
if "route" in uk and "stop_n" in uk["route"]:
    old = uk["route"]["stop_n"]
    uk["route"]["stop_n"] = old.replace("{n}", "{}")
    print(f"  Fixed uk.json route.stop_n: {old} -> {uk['route']['stop_n']}")
with open(uk_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(uk, f, indent=2, ensure_ascii=False)
    f.write("\n")

print("\nDone fixing placeholders.")
