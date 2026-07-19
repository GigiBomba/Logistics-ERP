#!/usr/bin/env python3
"""Final comprehensive translation for de.json, es.json, fr.json."""
import json, os, re

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def iter_leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from iter_leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_leaves(v, path + (i,))
    else:
        yield path, obj

def get_at(obj, path):
    for key in path:
        obj = obj[key]
    return obj

def set_at(obj, path, value):
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value

PRESERVE = {"ID","KM","VIN","EUR","N/A","CSV","PDF","OCR","GPS","API","CMR","KPI",
            "SMTP","DSO","SLA","SOC","GDPR","CUI","VAT","ETA","SMS","GBP","USD",
            "RON","JSON","BOM","UTF-8","DDD","TGD","POD","AI","COD"}

def should_translate(val):
    if not isinstance(val, str) or not val:
        return False
    if val.strip() in PRESERVE:
        return False
    if re.match(r"^\{.*\}$", val.strip()):
        return False
    return True

en = load_json(os.path.join(TRANS_DIR, "en.json"))

def build_bootstrap(tgt_data, en_data):
    pairs = {}
    def walk(t, e, p=""):
        if isinstance(t, dict) and isinstance(e, dict):
            for k in t:
                if k in e:
                    np = f"{p}.{k}" if p else k
                    walk(t[k], e[k], np)
        elif isinstance(t, list) and isinstance(e, list):
            for ti, ei in zip(t, e):
                if isinstance(ti, str) and isinstance(ei, str) and ti != ei:
                    pairs[ei] = ti
                elif isinstance(ti, (dict,list)) and isinstance(ei, (dict,list)):
                    walk(ti, ei, p)
        elif isinstance(t, str) and isinstance(e, str) and t != e:
            pairs[e] = t
    walk(tgt_data, en_data)
    return pairs

# =====================================================================
# SUPPLEMENTARY DICTIONARIES
# =====================================================================

FR_SUPP = {
    "Actions": "Actions",
    "Administration": "Administration",
    "Ajouter un entretien": "Ajouter un entretien",
    "BOXES 1-2": "CASES 1-2",
    "BOXES 13-17": "CASES 13-17",
    "BOXES 18-19": "CASES 18-19",
    "BOXES 21-24": "CASES 21-24",
    "BOXES 3-5": "CASES 3-5",
    "BOXES 6-7": "CASES 6-7",
    "BOXES 8-14": "CASES 8-14",
    "Browse": "Parcourir",
    "CMR": "CMR",
    "CSV": "CSV",
    "Clients": "Clients",
    "Concentration": "Concentration",
    "Configuration": "Configuration",
    "Contacts": "Contacts",
    "Danger": "Danger",
    "Date": "Date",
    "Description": "Description",
    "Destination": "Destination",
    "Diagnostics": "Diagnostics",
    "Distance": "Distance",
    "Distance (km)": "Distance (km)",
    "Doc #{}": "Doc #{}",
    "Documents": "Documents",
    "EMAIL": "EMAIL",
    "EMail": "Email",
    "ERP": "ERP",
    "ETA": "ETA",
    "Email": "Email",
    "Excellent": "Excellent",
    "Google Maps": "Google Maps",
    "IDENTIFICATION": "IDENTIFICATION",
    "ID": "ID",
    "Images": "Images",
    "Info": "Info",
    "Innovation": "Innovation",
    "KM": "KM",
    "LIVE": "LIVE",
    "L/100km": "L/100km",
    "Logo": "Logo",
    "Mihai Popescu": "Mihai Popescu",
    "N/A": "N/D",
    "Net": "Net",
    "Net 15": "Net 15",
    "Net 30": "Net 30",
    "Net 60": "Net 60",
    "Notes": "Notes",
    "OCR": "OCR",
    "OK": "OK",
    "Operion": "Operion",
    "Options": "Options",
    "PDF": "PDF",
    "PARTIES": "PARTIES",
    "POD": "POD",
    "Proformas": "Proformas",
    "Proforma": "Proforma",
    "RO12345678": "RO12345678",
    "Reliability": "Fiabilité",
    "SELECT": "SELECT",
    "Services": "Services",
    "Signature": "Signature",
    "Simple": "Simple",
    "Time": "Time",
    "Top 3": "Top 3",
    "Total": "Total",
    "Type": "Type",
    "VIN": "VIN",
    "Validation": "Validation",
    "contact@firma.ro": "contact@firma.fr",
    "minute": "minute",
    "minutes": "minutes",
    " km": " km",
    " kg": " kg",
    "John Smith": "John Smith",
    "CEO, Smith Logistics": "CEO, Smith Logistics",
    "Mihai Popescu": "Mihai Popescu",
    "Sarah Müller": "Sarah Müller",
    "Fleet Manager, TransLogistic": "Fleet Manager, TransLogistic",
    "Operations Director, EuroFreight": "Operations Director, EuroFreight",
    "Innovation": "Innovation",
    "Security": "Sécurité",
    "Transparency": "Transparence",
    "Partnership": "Partenariat",
    "Customer First": "Client d'abord",
    "Our Team": "Notre équipe",
    "Our Story": "Notre histoire",
    "Our Values": "Nos valeurs",
    "Our Mission": "Notre mission",
}

# Run translations
for code, supp in [("fr", FR_SUPP)]:
    tgt = load_json(os.path.join(TRANS_DIR, f"{code}.json"))
    boot = build_bootstrap(tgt, en)
    combined = dict(boot)
    combined.update(supp)
    
    count = 0
    for path, en_val in iter_leaves(en):
        if not should_translate(en_val):
            continue
        try:
            tgt_val = get_at(tgt, path)
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(tgt_val, str) and tgt_val == en_val:
            tr = combined.get(en_val)
            if tr:
                set_at(tgt, path, tr)
                count += 1
    
    save_json(os.path.join(TRANS_DIR, f"{code}.json"), tgt)
    print(f"{code}: translated {count} strings")

# Show final stats
print("\n=== FINAL COVERAGE ===")
for code in ["de", "es", "fr"]:
    tgt = load_json(os.path.join(TRANS_DIR, f"{code}.json"))
    total = 0; untranslated = 0
    for path, en_val in iter_leaves(en):
        if not should_translate(en_val):
            continue
        total += 1
        try:
            v = get_at(tgt, path)
        except:
            continue
        if isinstance(v, str) and v == en_val:
            untranslated += 1
    pct = round((1 - untranslated/total) * 100, 1) if total else 0
    print(f"  {code}.json: {pct}% ({total-untranslated}/{total}, {untranslated} untranslated)")
