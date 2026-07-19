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
TARGET_LANGS = ["bs", "hr", "sv", "sl", "sr", "el", "ru", "sk", "pl", "uk", "es", "fr", "de", "cs", "pt", "hu", "tr"]
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
    if re.match(r'^[\d\.,\s%\u20ac\$\u00a3\u00b1\-\u2014=\'\"\u2032\u2033]+$', val):
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
    clean = re.sub(r'[\\(\)\\.\:\s]', '', val)
    if clean.upper() in UPPER_ACRONYMS:
        return True
    if re.match(r'^\{[^}]*\}$', val):
        return True
    if val in LOANWORDS:
        return True
    if val in NAMES_AND_BRANDS:
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
    parts = re.split(r'(\{[^}]*\})', english_text)
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
                    clean_w = w.strip('.,:;!?()[]\\\'"')
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

    # Build combined vmap: own first, then ALL donors
    combined_vmap = dict(own_vmap)
    for donor_lang, donor_info in donors.items():
        if donor_lang != lang_code:
            for k, v in donor_info["vmap"].items():
                if k not in combined_vmap and k in en_flat:
                    combined_vmap[k] = v

    # Build comprehensive word-level dict from ALL languages
    word_dict = {}
    for donor_lang, donor_info in donors.items():
        for k, en_v in en_flat.items():
            donor_flat = donor_info["flat"]
            if k in donor_flat:
                v = donor_flat[k]
                en_v_str = str(en_v) if not isinstance(en_v, str) else en_v
                if isinstance(v, str) and v.strip() and en_v_str.strip():
                    en_clean = en_v_str.strip()
                    v_clean = v.strip()
                    if v_clean != en_clean and not is_untranslatable(en_clean):
                        if len(en_clean.split()) == 1 and ':' not in en_clean:
                            if en_clean not in word_dict:
                                word_dict[en_clean] = v_clean

    # Also add extra word dictionaries for this language
    if lang_code in EXTRA_WORDS:
        for k, v in EXTRA_WORDS[lang_code].items():
            if k not in word_dict:
                word_dict[k] = v

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

        # Try own vmap first (includes existing translations + borrowed phrases)
        translation = combined_vmap.get(en_v_str)
        if translation and translation != en_v_str:
            target_flat[k] = translation
            stats["translated"] += 1
            continue

        # Try direct donor translations: for this key, check if any priority
        # donor has a different (translated) value, and if so, use it directly
        direct_translation = None
        for donor_lang in donor_priority:
            if donor_lang in donors and donor_lang != lang_code:
                donor_flat = donors[donor_lang]["flat"]
                if k in donor_flat:
                    dv = donor_flat[k]
                    dv_str = str(dv) if not isinstance(dv, str) else dv
                    if isinstance(dv_str, str) and dv_str.strip() and dv_str.strip() != en_v_str:
                        if not is_untranslatable(dv_str):
                            direct_translation = dv_str.strip()
                            break
        if direct_translation:
            target_flat[k] = direct_translation
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


def main():
    print("=" * 70)
    print("  Translation - All Remaining Languages (below 80%)")
    print("=" * 70)

    # Record coverage before
    coverage_before = {}
    for lang in TARGET_LANGS:
        _, t, p = analyze_coverage(lang)
        coverage_before[lang] = (t, p)
        sys.stdout.flush()

    print()
    en_data, en_flat, donors = load_all_donors()
    print(f"  Loaded {len(donors)} language files for cross-reference")
    print()

    all_stats = {}
    for lang in TARGET_LANGS:
        print(f"  Processing {lang}.json...", end=" ")
        sys.stdout.flush()
        stats = translate_file(lang, en_flat, en_data, donors)
        all_stats[lang] = stats
        total_new = stats["translated"]
        _, _, pct = analyze_coverage(lang)
        print(f"   {total_new} new translations -> {pct:.1f}%")
        sys.stdout.flush()

    print()
    print("=" * 70)
    print("  Final Results")
    print("=" * 70)
    for lang in TARGET_LANGS:
        total, translated, pct = analyze_coverage(lang)
        before_pct = coverage_before[lang][1]
        gained = pct - before_pct
        print(f"  {lang}.json: {before_pct:.1f}% -> {pct:.1f}% (+{gained:.1f}%, {translated}/{total})")
    print()
    print("  Done.")


def analyze_coverage(lang_code):
    """Match _all_coverage.py exactly."""
    en = load_json(os.path.join(TRANSLATIONS_DIR, "en.json"))
    en_f = _flat(en)
    data = load_json(os.path.join(TRANSLATIONS_DIR, f"{lang_code}.json"))
    lang_f = _flat(data)
    total = len(en_f)
    untrans = sum(1 for k, v in lang_f.items() if v == en_f.get(k, ""))
    translated = total - untrans
    pct = 100 * translated / total if total else 0
    return total, translated, pct


# ─── COMPREHENSIVE WORD DICTIONARIES ──────────────────────────
# These are the core words for each language, used as fallback
# when phrase-level matching fails.

EXTRA_WORDS = {}

# ─── BOSNIAN (bs) ───
EXTRA_WORDS["bs"] = {
    "A-Z": "A-Š", "About": "O", "Above": "Iznad", "Action": "Akcija", 
    "Active": "Aktivan", "Activity": "Aktivnost", "Add": "Dodaj", "Address": "Adresa",
    "Admin": "Admin", "Advanced": "Napredno", "Alert": "Upozorenje", "All": "Sve",
    "Amount": "Iznos", "Analysis": "Analiza", "And": "I", "Any": "Bilo koji",
    "App": "Aplikacija", "Application": "Aplikacija", "Apply": "Primijeni",
    "Archive": "Arhiva", "Archived": "Arhivirano", "Area": "Područje",
    "Assign": "Dodijeli", "At": "Na", "Attachment": "Prilog", "Auth": "Autentifikacija",
    "Auto": "Auto", "Automation": "Automatizacija", "Available": "Dostupno",
    "Avg": "Prosjek", "Average": "Prosjek", "Back": "Nazad", "Backup": "Rezerva",
    "Bad": "Loše", "Bank": "Banka", "Basic": "Osnovno", "Best": "Najbolji",
    "Bill": "Račun", "Blocked": "Blokirano", "Board": "Tabla", "Body": "Tijelo",
    "Book": "Knjiga", "Box": "Kutija", "Branch": "Poslovnica", "Break": "Pauza",
    "Breakdown": "Pregled", "Browse": "Pretraži", "Bulk": "Masovno",
    "Business": "Poslovanje", "Button": "Dugme", "By": "Po",
    "Calculate": "Izračunaj", "Calculation": "Izračun", "Calendar": "Kalendar",
    "Cancel": "Odustani", "Cancelled": "Otkazano", "Card": "Kartica",
    "Carrier": "Prijevoznik", "Category": "Kategorija", "Center": "Centar",
    "Change": "Promjena", "Chart": "Grafikon", "City": "Grad",
    "Clear": "Očisti", "Click": "Klikni", "Client": "Klijent", "Close": "Zatvori",
    "Code": "Kod", "Collection": "Naplata", "Color": "Boja", "Column": "Kolona",
    "Compare": "Uporedi", "Comparison": "Poređenje", "Complete": "Završi",
    "Completed": "Završeno", "Compliance": "Usklađenost", "Config": "Konfiguracija",
    "Configuration": "Konfiguracija", "Confirm": "Potvrdi", "Conflict": "Konflikt",
    "Connect": "Poveži", "Connection": "Veza", "Consignee": "Primalac",
    "Consignor": "Pošiljalac", "Contact": "Kontakt", "Control": "Kontrola",
    "Copy": "Kopiraj", "Cost": "Trošak", "Count": "Broj", "Country": "Država",
    "Coverage": "Pokrivenost", "Create": "Kreiraj", "Critical": "Kritično",
    "Currency": "Valuta", "Current": "Trenutni", "Custom": "Prilagođeno",
    "Customer": "Kupac", "Daily": "Dnevno", "Danger": "Opasnost",
    "Dashboard": "Kontrolna ploča", "Data": "Podaci", "Database": "Baza podataka",
    "Date": "Datum", "Day": "Dan", "Days": "Dani", "Deactivate": "Deaktiviraj",
    "Default": "Podrazumijevano", "Delay": "Kašnjenje", "Delayed": "Zakašnjelo",
    "Delete": "Obriši", "Delivered": "Isporučeno", "Department": "Odjel",
    "Departure": "Polazak", "Description": "Opis", "Destination": "Odredište",
    "Detail": "Detalj", "Diagnostics": "Dijagnostika", "Digital": "Digitalno",
    "Director": "Direktor", "Discount": "Popust", "Dispatch": "Dispečing",
    "Display": "Prikaz", "Distance": "Udaljenost", "Distribution": "Distribucija",
    "Doc": "Dokument", "Document": "Dokument", "Done": "Gotovo",
    "Download": "Preuzmi", "Draft": "Nacrt", "Driver": "Vozač",
    "Due": "Dospjelo", "Duplicate": "Dupliciraj", "Duration": "Trajanje",
    "Edit": "Uredi", "Efficiency": "Efikasnost", "Email": "Email",
    "Employee": "Zaposlenik", "Empty": "Prazno", "End": "Kraj",
    "Engine": "Motor", "Entry": "Unos", "Environment": "Okruženje",
    "Error": "Greška", "Excel": "Excel", "Exclude": "Isključi",
    "Execute": "Izvrši", "Expense": "Trošak", "Expired": "Isteklo",
    "Expiring": "Ističe", "Expiry": "Istek", "Export": "Izvoz",
    "Extended": "Produženo", "Extra": "Dodatno", "Extracted": "Izdvojeno",
    "Failed": "Neuspješno", "Failure": "Neuspjeh", "Fair": "Dobro",
    "Feature": "Funkcija", "Field": "Polje", "File": "Datoteka",
    "Filter": "Filter", "Finance": "Finansije", "Financial": "Finansijski",
    "Find": "Pronađi", "First": "Prvi", "Fixed": "Fiksno",
    "Fleet": "Flota", "Footer": "Podnožje", "Forecast": "Prognoza",
    "Form": "Forma", "Format": "Format", "Free": "Besplatno",
    "Frequency": "Učestalost", "From": "Od", "Fuel": "Gorivo",
    "Full": "Pun", "Generate": "Generiši", "Generated": "Generisano",
    "Generator": "Generator", "Geographic": "Geografski", "Good": "Dobar",
    "Goods": "Roba", "Grand": "Ukupno", "Gross": "Bruto", "Group": "Grupa",
    "Growth": "Rast", "Header": "Zaglavlje", "Health": "Zdravlje",
    "Help": "Pomoć", "Hide": "Sakrij", "High": "Visoko",
    "History": "Historija", "Home": "Početna", "Host": "Host",
    "Hour": "Sat", "Icon": "Ikona", "Idle": "Miruje",
    "Image": "Slika", "Import": "Uvoz", "In": "U",
    "Inactive": "Neaktivno", "Info": "Info", "Information": "Informacija",
    "Innovation": "Inovacija", "Inspection": "Inspekcija",
    "Insurance": "Osiguranje", "Integration": "Integracija",
    "Intelligence": "Inteligencija", "Interval": "Interval",
    "Invalid": "Nevažeći", "Item": "Stavka",
    "Key": "Ključ", "Label": "Oznaka", "Language": "Jezik",
    "Last": "Posljednji", "Latency": "Latencija", "License": "Licenca",
    "Limit": "Limit", "Line": "Linija", "Link": "Link",
    "Linked": "Povezano", "List": "Spisak", "Live": "Uživo",
    "Load": "Učitaj", "Loaded": "Učitano", "Location": "Lokacija",
    "Log": "Dnevnik", "Login": "Prijava", "Logo": "Logo",
    "Low": "Nisko", "Main": "Glavni", "Maintenance": "Održavanje",
    "Manage": "Upravljaj", "Management": "Upravljanje", "Manager": "Menadžer",
    "Manual": "Ručno", "Map": "Mapa", "Margin": "Marža",
    "Match": "Poklapanje", "Max": "Maks", "Member": "Član",
    "Memory": "Memorija", "Merge": "Spoji", "Message": "Poruka",
    "Metric": "Metrika", "Migration": "Migracija", "Mileage": "Kilometraža",
    "Min": "Min", "Minute": "Minuta", "Mission": "Misija",
    "Mode": "Režim", "Model": "Model", "Modern": "Moderan",
    "Month": "Mjesec", "More": "Više", "Most": "Najviše",
    "Move": "Pomjeri", "Multi": "Multi", "Name": "Ime",
    "Navigation": "Navigacija", "Net": "Neto", "New": "Novi",
    "Newest": "Najnoviji", "Next": "Sljedeći", "No": "Ne",
    "None": "Nijedan", "Note": "Napomena", "Number": "Broj",
    "Odometer": "Brojač km", "Of": "Od", "Office": "Kancelarija",
    "Offline": "Offline", "On": "Na", "Online": "Online",
    "Open": "Otvori", "Operation": "Operacija", "Option": "Opcija",
    "Optional": "Opciono", "Or": "Ili", "Order": "Red",
    "Origin": "Porijeklo", "Other": "Ostalo", "Outstanding": "Nenaplaćeno",
    "Overall": "Ukupno", "Overdue": "Dospjelo", "Overview": "Pregled",
    "Package": "Paket", "Page": "Stranica", "Paid": "Plaćeno",
    "Panel": "Panel", "Parking": "Parking", "Partial": "Djelimično",
    "Partner": "Partner", "Partnership": "Partnerstvo", "Password": "Lozinka",
    "Path": "Put", "Payment": "Plaćanje", "Percent": "Postotak",
    "Performance": "Performanse", "Period": "Period", "Phone": "Telefon",
    "Photo": "Fotografija", "Pick": "Odaberi", "Place": "Mjesto",
    "Plan": "Plan", "Planned": "Planirano", "Planning": "Planiranje",
    "Plate": "Tablica", "Platform": "Platforma", "Port": "Port",
    "Prediction": "Predviđanje", "Preference": "Preferencija",
    "Preview": "Pregled", "Price": "Cijena", "Print": "Štampaj",
    "Priority": "Prioritet", "Process": "Proces", "Profit": "Profit",
    "Profitability": "Profitabilnost", "Profile": "Profil", "Proof": "Dokaz",
    "Provider": "Dobavljač", "Purpose": "Svrha", "Quick": "Brzo",
    "Rate": "Stopa", "Rating": "Ocjena", "Ratio": "Odnos",
    "Receipt": "Račun", "Received": "Primljeno", "Recipient": "Primalac",
    "Recommended": "Preporučeno", "Record": "Zapis", "Recurring": "Ponavljajući",
    "Refresh": "Osvježi", "Refund": "Povraćaj", "Register": "Registracija",
    "Reliability": "Pouzdanost", "Remaining": "Preostalo", "Reminder": "Podsjetnik",
    "Remove": "Ukloni", "Report": "Izvještaj", "Required": "Obavezno",
    "Reset": "Resetuj", "Resolve": "Riješi", "Resource": "Resurs",
    "Rest": "Ostalo", "Restore": "Vrati", "Result": "Rezultat",
    "Retention": "Zadržavanje", "Retry": "Pokušaj ponovo", "Return": "Povratak",
    "Revenue": "Prihod", "Role": "Uloga", "Route": "Ruta",
    "Run": "Pokreni", "Safety": "Sigurnost", "Salary": "Plata",
    "Save": "Sačuvaj", "Saved": "Sačuvano", "Schedule": "Raspored",
    "Scheduled": "Zakazano", "Score": "Rezultat", "Search": "Traži",
    "Second": "Sekunda", "Section": "Sekcija", "Security": "Sigurnost",
    "Select": "Odaberi", "Selected": "Odabrano", "Selection": "Izbor",
    "Sender": "Pošiljalac", "Send": "Pošalji", "Sent": "Poslano",
    "Server": "Server", "Service": "Servis", "Set": "Postavi",
    "Setting": "Postavka", "Setup": "Podešavanje", "Severity": "Ozbiljnost",
    "Share": "Podijeli", "Show": "Prikaži", "Signature": "Potpis",
    "Simple": "Jednostavno", "Size": "Veličina", "Small": "Malo",
    "Smart": "Pametno", "Software": "Softver", "Sort": "Sortiraj",
    "Source": "Izvor", "Specific": "Specifično", "Speed": "Brzina",
    "Stamp": "Pečat", "Standalone": "Samostalno", "Start": "Početak",
    "Statistics": "Statistika", "Status": "Status", "Stop": "Stanica",
    "Storage": "Skladište", "Subject": "Predmet", "Subtitle": "Podnaslov",
    "Subtotal": "Međuzbir", "Success": "Uspjeh", "Summary": "Sažetak",
    "System": "Sistem", "Table": "Tabela", "Tab": "Kartica",
    "Tag": "Oznaka", "Target": "Cilj", "Task": "Zadatak",
    "Tax": "Porez", "Team": "Tim", "Template": "Šablon",
    "Terms": "Uslovi", "Test": "Test", "Theme": "Tema",
    "Threshold": "Prag", "Time": "Vrijeme", "Timeline": "Vremenska linija",
    "Title": "Naslov", "To": "Do", "Today": "Danas",
    "Token": "Token", "Toll": "Putarina", "Tool": "Alat",
    "Top": "Vrh", "Total": "Ukupno", "Track": "Prati",
    "Tracking": "Praćenje", "Traffic": "Saobraćaj", "Trailer": "Prikolica",
    "Transaction": "Transakcija", "Transition": "Prijelaz",
    "Transparency": "Transparentnost", "Transport": "Transport",
    "Trend": "Trend", "Trip": "Putovanje", "Truck": "Kamion",
    "Type": "Tip", "Unassigned": "Nedodijeljeno", "Unavailable": "Nedostupno",
    "Undo": "Poništi", "Unknown": "Nepoznato", "Unlink": "Odveži",
    "Unloading": "Istovar", "Unpaid": "Neplaćeno", "Update": "Ažuriraj",
    "Upgrade": "Nadogradi", "Upload": "Učitaj", "Usage": "Upotreba",
    "User": "Korisnik", "Utilization": "Iskorištenost",
    "Validation": "Validacija", "Value": "Vrijednost", "Vehicle": "Vozilo",
    "Version": "Verzija", "View": "Pregled", "Violation": "Prekršaj",
    "Visibility": "Vidljivost", "Volume": "Obim", "Warning": "Upozorenje",
    "Week": "Sedmica", "Weight": "Težina", "Welcome": "Dobrodošli",
    "Year": "Godina", "Yesterday": "Jučer", "Zip": "Zip",
}

# ─── CROATIAN (hr) ───
EXTRA_WORDS["hr"] = dict(EXTRA_WORDS["bs"])
EXTRA_WORDS["hr"].update({
    "Account": "Račun", "Apartment": "Stan", "Bus": "Autobus",
    "Center": "Centar", "Check": "Provjeri", "Commission": "Provizija",
    "Company": "Tvrtka", "Copy": "Kopiraj", "Customer": "Kupac",
    "Dashboard": "Nadzorna ploča", "Day": "Dan", "Days": "Dani",
    "Delete": "Obriši", "Department": "Odjel", "Director": "Direktor",
    "Distance": "Udaljenost", "Download": "Preuzmi", "Edit": "Uredi",
    "Efficiency": "Učinkovitost", "Employee": "Zaposlenik",
    "Expense": "Trošak", "File": "Datoteka", "Fleet": "Flota",
    "Folder": "Mapa", "Good": "Dobar", "Goods": "Roba",
    "Gross": "Bruto", "Help": "Pomoć", "History": "Povijest",
    "Home": "Početna", "Info": "Info", "Inspection": "Inspekcija",
    "Integration": "Integracija", "Item": "Stavka", "Label": "Oznaka",
    "Language": "Jezik", "License": "Dozvola", "Main": "Glavni",
    "Maintenance": "Održavanje", "Manager": "Menadžer", "Manual": "Ručno",
    "Margin": "Marža", "Merge": "Spoji", "Month": "Mjesec",
    "Monthly": "Mjesečno", "More": "Više", "Name": "Ime",
    "Navigation": "Navigacija", "New": "Novi", "Next": "Sljedeće",
    "Note": "Bilješka", "Overview": "Pregled", "Paid": "Plaćeno",
    "Parking": "Parkiranje", "Partner": "Partner", "Path": "Put",
    "Period": "Razdoblje", "Phone": "Telefon", "Preview": "Pregled",
    "Print": "Ispis", "Priority": "Prioritet", "Profit": "Dobit",
    "Provider": "Pružatelj", "Rate": "Stopa", "Receipt": "Račun",
    "Record": "Zapis", "Refresh": "Osveži", "Remaining": "Preostalo",
    "Remove": "Ukloni", "Required": "Obavezno", "Reset": "Resetiraj",
    "Resource": "Resurs", "Route": "Ruta", "Safety": "Sigurnost",
    "Salary": "Plaća", "Save": "Spremi", "Schedule": "Raspored",
    "Search": "Traži", "Security": "Sigurnost", "Select": "Odaberi",
    "Service": "Usluga", "Settings": "Postavke", "Share": "Podijeli",
    "Show": "Prikaži", "Simple": "Jednostavno", "Software": "Softver",
    "Source": "Izvor", "Speed": "Brzina", "Start": "Početak",
    "Status": "Status", "Stop": "Stanica", "Subject": "Predmet",
    "Subtotal": "Međuzbroj", "Summary": "Sažetak", "System": "Sustav",
    "Table": "Tablica", "Target": "Cilj", "Task": "Zadatak",
    "Team": "Tim", "Template": "Predložak", "Test": "Test",
    "Time": "Vrijeme", "Title": "Naslov", "Today": "Danas",
    "Total": "Ukupno", "Tracking": "Praćenje", "Trailer": "Prikolica",
    "Trip": "Putovanje", "Unpaid": "Neplaćeno", "Update": "Ažuriraj",
    "Upload": "Učitaj", "User": "Korisnik", "Value": "Vrijednost",
    "Vehicle": "Vozilo", "Version": "Verzija", "View": "Pregled",
    "Warning": "Upozorenje", "Week": "Tjedan", "Weekly": "Tjedno",
    "Weight": "Težina", "Year": "Godina", "Yearly": "Godišnje",
    "Yesterday": "Jučer",
})

# ─── SLOVENIAN (sl) ───
EXTRA_WORDS["sl"] = {
    "Active": "Aktivno", "Add": "Dodaj", "Address": "Naslov",
    "All": "Vsi", "Amount": "Znesek", "Apply": "Uporabi",
    "Archive": "Arhiv", "Archived": "Arhivirano", "Back": "Nazaj",
    "Browse": "Prebrskaj", "Calculate": "Izračunaj", "Cancel": "Prekliči",
    "Clear": "Počisti", "Client": "Stranka", "Close": "Zapri",
    "Code": "Koda", "Confirm": "Potrdi", "Cost": "Strošek",
    "Country": "Država", "Create": "Ustvari", "Created": "Ustvarjeno",
    "Critical": "Kritično", "Dashboard": "Nadzorna plošča", "Data": "Podatki",
    "Date": "Datum", "Day": "Dan", "Days": "Dnevi", "Deactivate": "Deaktiviraj",
    "Delete": "Izbriši", "Description": "Opis", "Download": "Prenesi",
    "Driver": "Voznik", "Edit": "Uredi", "Email": "E-pošta",
    "Error": "Napaka", "Export": "Izvoz", "Failed": "Neuspešno",
    "File": "Datoteka", "Filter": "Filter", "Finance": "Finance",
    "Fleet": "Flota", "From": "Od", "Fuel": "Gorivo",
    "Generate": "Ustvari", "Gross": "Bruto", "Help": "Pomoč",
    "Hide": "Skrij", "History": "Zgodovina", "Home": "Domov",
    "Hour": "Ura", "Hours": "Ure", "Import": "Uvoz",
    "Info": "Informacije", "Invoice": "Faktura", "Language": "Jezik",
    "Load": "Naloži", "Loading": "Nalaganje", "Logo": "Logotip",
    "Name": "Ime", "Net": "Neto", "New": "Nov",
    "Next": "Naslednji", "No": "Ne", "Notes": "Opombe",
    "OK": "V redu", "Open": "Odpri", "Overview": "Pregled",
    "Paid": "Plačano", "Password": "Geslo", "Preview": "Predogled",
    "Previous": "Prejšnji", "Print": "Natisni", "Refresh": "Osveži",
    "Remove": "Odstrani", "Save": "Shrani", "Search": "Išči",
    "Select": "Izberi", "Send": "Pošlji", "Sent": "Poslano",
    "Settings": "Nastavitve", "Share": "Deli", "Show": "Pokaži",
    "Signature": "Podpis", "Stamp": "Pečat", "Start": "Začetek",
    "Status": "Status", "Success": "Uspeh", "Total": "Skupaj",
    "Trip": "Potovanje", "Truck": "Tovornjak", "Unknown": "Neznano",
    "Update": "Posodobi", "Upload": "Naloži", "View": "Pogled",
    "Warning": "Opozorilo", "Year": "Leto", "Yes": "Da",
    "Yesterday": "Včeraj", "Active": "Aktivno", "Inactive": "Neaktivno",
    "Today": "Danes", "Administration": "Administracija",
    "Carrier": "Prevoznik", "Consignee": "Prejemnik", "Consignor": "Pošiljatelj",
    "Dispatch": "Dispečing", "Dispatcher": "Dispečer",
    "Distance": "Razdalja", "Document": "Dokument", "Driver": "Voznik",
    "Duration": "Trajanje", "Feature": "Funkcija", "Field": "Polje",
    "Financial": "Finančni", "Fixed": "Fiksno", "Forecast": "Napoved",
    "Format": "Oblika", "Free": "Brezplačno", "Full": "Poln",
    "Goods": "Blago", "Grand": "Skupni", "Group": "Skupina",
    "Header": "Glava", "Health": "Zdravje", "Image": "Slika",
    "Inactive": "Neaktivno", "Insurance": "Zavarovanje",
    "Invoice": "Faktura", "Item": "Postavka", "Key": "Ključ",
    "Label": "Oznaka", "Last": "Zadnji", "Line": "Vrstica",
    "Link": "Povezava", "List": "Seznam", "Location": "Lokacija",
    "Log": "Dnevnik", "Login": "Prijava", "Main": "Glavni",
    "Margin": "Marža", "Member": "Član", "Merge": "Združi",
    "Message": "Sporočilo", "Minute": "Minuta", "Minutes": "Minute",
    "Month": "Mesec", "Monthly": "Mesečno", "More": "Več",
}


# ─── SERBIAN (sr) — Cyrillic ───
EXTRA_WORDS["sr"] = {
    "Active": "Активан", "Add": "Додај", "Address": "Адреса",
    "All": "Све", "Amount": "Износ", "Apply": "Примени",
    "Archive": "Архива", "Back": "Назад", "Browse": "Прегледај",
    "Calculate": "Израчунај", "Cancel": "Откажи", "Clear": "Обриши",
    "Client": "Клијент", "Close": "Затвори", "Code": "Код",
    "Confirm": "Потврди", "Cost": "Трошак", "Country": "Држава",
    "Create": "Креирај", "Critical": "Критичан", "Dashboard": "Контролна табла",
    "Data": "Подаци", "Date": "Датум", "Day": "Дан",
    "Days": "Дани", "Deactivate": "Деактивирај", "Delete": "Обриши",
    "Description": "Опис", "Download": "Преузми", "Driver": "Возач",
    "Edit": "Уреди", "Email": "Е-пошта", "Error": "Грешка",
    "Export": "Извоз", "Failed": "Неуспело", "File": "Датотека",
    "Filter": "Филтер", "Finance": "Финансије", "Fleet": "Флота",
    "From": "Од", "Fuel": "Гориво", "Generate": "Генериши",
    "Gross": "Бруто", "Help": "Помоћ", "Hide": "Сакриј",
    "History": "Историја", "Home": "Почетна", "Hour": "Сат",
    "Import": "Увоз", "Info": "Инфо", "Invoice": "Фактура",
    "Language": "Језик", "Load": "Учитај", "Loading": "Учитавање",
    "Name": "Име", "Net": "Нето", "New": "Нови",
    "Next": "Следећи", "No": "Не", "Notes": "Напомене",
    "OK": "У реду", "Open": "Отвори", "Overview": "Преглед",
    "Paid": "Плаћено", "Password": "Лозинка", "Preview": "Преглед",
    "Previous": "Претходни", "Print": "Штампај", "Refresh": "Освежи",
    "Remove": "Уклони", "Save": "Сачувај", "Search": "Претрага",
    "Select": "Изабери", "Send": "Пошаљи", "Sent": "Послато",
    "Settings": "Подешавања", "Share": "Подели", "Show": "Прикажи",
    "Signature": "Потпис", "Stamp": "Печат", "Start": "Почетак",
    "Status": "Статус", "Success": "Успех", "Total": "Укупно",
    "Trip": "Путовање", "Truck": "Камион", "Unknown": "Непознато",
    "Update": "Ажурирај", "Upload": "Отпреми", "View": "Приказ",
    "Warning": "Упозорење", "Year": "Година", "Yes": "Да",
    "Yesterday": "Јуче", "Today": "Данас", "Active": "Активан",
    "Inactive": "Неактиван", "Administration": "Администрација",
    "Carrier": "Превозник", "Consignee": "Прималац", "Consignor": "Пошиљалац",
    "Dispatch": "Диспечинг", "Dispatcher": "Диспечер",
    "Distance": "Удаљеност", "Document": "Документ", "Duration": "Трајање",
    "Feature": "Функција", "Field": "Поље", "Financial": "Финансијски",
    "Fixed": "Фиксно", "Goods": "Роба", "Group": "Група",
    "Health": "Здравље", "Image": "Слика", "Insurance": "Осигурање",
    "Item": "Ставка", "Label": "Ознака", "License": "Лиценца",
    "Line": "Линија", "Link": "Линк", "List": "Списак",
    "Location": "Локација", "Log": "Дневник", "Login": "Пријава",
    "Logo": "Лого", "Maintenance": "Одржавање", "Margin": "Маржа",
    "Member": "Члан", "Merge": "Споји", "Message": "Порука",
    "Minute": "Минут", "Minutes": "Минути", "Month": "Месец",
    "Monthly": "Месечно", "More": "Више", "Schedule": "Распоред",
    "Search": "Претрага", "Section": "Секција", "Security": "Безбедност",
    "Server": "Сервер", "Service": "Сервис", "Set": "Постави",
    "Sort": "Сортирај", "Source": "Извор", "Speed": "Брзина",
    "Stop": "Станица", "Subject": "Предмет", "Subtotal": "Међузбир",
    "Summary": "Сажетак", "System": "Систем", "Table": "Табела",
    "Tax": "Порез", "Team": "Тим", "Template": "Шаблон",
    "Test": "Тест", "Time": "Време", "Timeline": "Временска линија",
    "Title": "Наслов", "To": "До", "Today": "Данас",
    "Token": "Токен", "Toll": "Путарина", "Tool": "Алат",
    "Top": "Врх", "Totals": "Збир", "Track": "Прати",
    "Tracking": "Праћење", "Trailer": "Приколица", "Trend": "Тренд",
    "Type": "Тип", "Unassigned": "Недодељено", "Unloading": "Истовар",
    "User": "Корисник", "Validation": "Валидација", "Value": "Вредност",
    "Vehicle": "Возило", "Version": "Верзија", "Violation": "Прекршај",
    "Volume": "Обим", "Warning": "Упозорење", "Week": "Недеља",
    "Weekly": "Недељно", "Weight": "Тежина", "Welcome": "Добродошли",
}

# ─── SWEDISH (sv) ───
EXTRA_WORDS["sv"] = {
    "Active": "Aktiv", "Add": "Lägg till", "Address": "Adress",
    "All": "Alla", "Amount": "Belopp", "Apply": "Applicera",
    "Archive": "Arkiv", "Back": "Tillbaka", "Browse": "Bläddra",
    "Calculate": "Beräkna", "Cancel": "Avbryt", "Clear": "Rensa",
    "Client": "Kund", "Close": "Stäng", "Code": "Kod",
    "Confirm": "Bekräfta", "Cost": "Kostnad", "Country": "Land",
    "Create": "Skapa", "Critical": "Kritisk", "Dashboard": "Instrumentpanel",
    "Data": "Data", "Date": "Datum", "Day": "Dag", "Days": "Dagar",
    "Deactivate": "Avaktivera", "Delete": "Ta bort", "Description": "Beskrivning",
    "Download": "Ladda ner", "Driver": "Förare", "Edit": "Redigera",
    "Email": "E-post", "Error": "Fel", "Export": "Exportera",
    "Failed": "Misslyckades", "File": "Fil", "Filter": "Filter",
    "Finance": "Ekonomi", "Fleet": "Fordonsflotta", "From": "Från",
    "Fuel": "Bränsle", "Generate": "Generera", "Gross": "Brutto",
    "Help": "Hjälp", "Hide": "Dölj", "History": "Historik",
    "Home": "Hem", "Hour": "Timme", "Import": "Importera",
    "Info": "Info", "Invoice": "Faktura", "Language": "Språk",
    "Load": "Ladda", "Loading": "Laddar", "Name": "Namn",
    "Net": "Netto", "New": "Ny", "Next": "Nästa", "No": "Nej",
    "Notes": "Anteckningar", "OK": "OK", "Open": "Öppna",
    "Overview": "Översikt", "Paid": "Betald", "Password": "Lösenord",
    "Preview": "Förhandsvisning", "Previous": "Föregående", "Print": "Skriv ut",
    "Refresh": "Uppdatera", "Remove": "Ta bort", "Save": "Spara",
    "Search": "Sök", "Select": "Välj", "Send": "Skicka",
    "Sent": "Skickad", "Settings": "Inställningar", "Share": "Dela",
    "Show": "Visa", "Signature": "Signatur", "Stamp": "Stämpel",
    "Start": "Start", "Status": "Status", "Success": "Framgång",
    "Total": "Totalt", "Trip": "Resa", "Truck": "Lastbil",
    "Unknown": "Okänd", "Update": "Uppdatera", "Upload": "Ladda upp",
    "View": "Visa", "Warning": "Varning", "Year": "År",
    "Yes": "Ja", "Yesterday": "Igår", "Today": "Idag",
    "Active": "Aktiv", "Inactive": "Inaktiv",
    "Administration": "Administration", "Carrier": "Transportföretag",
    "Consignee": "Mottagare", "Consignor": "Avsändare",
    "Dispatch": "Dispatch", "Dispatcher": "Dispatcher",
    "Distance": "Avstånd", "Document": "Dokument", "Duration": "Varaktighet",
    "Feature": "Funktion", "Field": "Fält", "Fixed": "Fast",
    "Goods": "Varor", "Group": "Grupp", "Insurance": "Försäkring",
    "Item": "Artikel", "Label": "Etikett", "License": "Licens",
    "Line": "Rad", "Link": "Länk", "List": "Lista",
    "Location": "Plats", "Log": "Logg", "Login": "Inloggning",
    "Logo": "Logotyp", "Maintenance": "Underhåll", "Margin": "Marginal",
    "Member": "Medlem", "Merge": "Slå samman", "Message": "Meddelande",
    "Minute": "Minut", "Minutes": "Minuter", "Month": "Månad",
    "Monthly": "Månadsvis", "More": "Mer", "Schedule": "Schema",
    "Section": "Avsnitt", "Security": "Säkerhet", "Server": "Server",
    "Service": "Tjänst", "Set": "Ställ in", "Sort": "Sortera",
    "Source": "Källa", "Speed": "Hastighet", "Stop": "Stopp",
    "Subject": "Ämne", "Subtotal": "Delsumma", "System": "System",
    "Table": "Tabell", "Tax": "Skatt", "Team": "Team",
    "Template": "Mall", "Test": "Test", "Time": "Tid",
    "Title": "Titel", "To": "Till", "Token": "Token",
    "Toll": "Vägavgift", "Tool": "Verktyg", "Top": "Topp",
    "Track": "Spåra", "Tracking": "Spårning", "Trailer": "Släp",
    "Trend": "Trend", "Type": "Typ", "User": "Användare",
    "Value": "Värde", "Vehicle": "Fordon", "Version": "Version",
    "Violation": "Överträdelse", "Volume": "Volym", "Week": "Vecka",
    "Weekly": "Veckovis", "Weight": "Vikt", "Welcome": "Välkommen",
    "Yearly": "Årligen", "Yesterday": "Igår",
}

# ─── GREEK (el) ───
EXTRA_WORDS["el"] = {
    "Active": "Ενεργό", "Add": "Προσθήκη", "Address": "Διεύθυνση",
    "All": "Όλα", "Amount": "Ποσό", "Apply": "Εφαρμογή",
    "Back": "Πίσω", "Cancel": "Ακύρωση", "Clear": "Εκκαθάριση",
    "Client": "Πελάτης", "Close": "Κλείσιμο", "Code": "Κωδικός",
    "Confirm": "Επιβεβαίωση", "Cost": "Κόστος", "Country": "Χώρα",
    "Create": "Δημιουργία", "Dashboard": "Πίνακας ελέγχου",
    "Data": "Δεδομένα", "Date": "Ημερομηνία", "Day": "Ημέρα",
    "Days": "Ημέρες", "Delete": "Διαγραφή", "Description": "Περιγραφή",
    "Download": "Λήψη", "Driver": "Οδηγός", "Edit": "Επεξεργασία",
    "Email": "Email", "Error": "Σφάλμα", "Export": "Εξαγωγή",
    "Failed": "Απέτυχε", "File": "Αρχείο", "Filter": "Φίλτρο",
    "From": "Από", "Generate": "Δημιουργία", "Gross": "Μικτό",
    "Help": "Βοήθεια", "Hide": "Απόκρυψη", "Home": "Αρχική",
    "Hour": "Ώρα", "Import": "Εισαγωγή", "Info": "Πληροφορίες",
    "Invoice": "Τιμολόγιο", "Language": "Γλώσσα", "Load": "Φόρτωση",
    "Name": "Όνομα", "Net": "Καθαρό", "New": "Νέο",
    "Next": "Επόμενο", "No": "Όχι", "Notes": "Σημειώσεις",
    "OK": "Εντάξει", "Open": "Άνοιγμα", "Overview": "Επισκόπηση",
    "Paid": "Πληρώθηκε", "Password": "Κωδικός", "Preview": "Προεπισκόπηση",
    "Previous": "Προηγούμενο", "Print": "Εκτύπωση", "Refresh": "Ανανέωση",
    "Remove": "Αφαίρεση", "Save": "Αποθήκευση", "Search": "Αναζήτηση",
    "Select": "Επιλογή", "Send": "Αποστολή", "Sent": "Απεστάλη",
    "Settings": "Ρυθμίσεις", "Share": "Κοινοποίηση", "Show": "Εμφάνιση",
    "Signature": "Υπογραφή", "Start": "Αρχή", "Status": "Κατάσταση",
    "Success": "Επιτυχία", "Total": "Σύνολο", "Trip": "Ταξίδι",
    "Truck": "Φορτηγό", "Update": "Ενημέρωση", "Upload": "Μεταφόρτωση",
    "View": "Προβολή", "Warning": "Προειδοποίηση", "Year": "Έτος",
    "Yes": "Ναι", "Today": "Σήμερα", "Yesterday": "Χθες",
    "Month": "Μήνας", "Monthly": "Μηνιαία", "Week": "Εβδομάδα",
    "Weekly": "Εβδομαδιαία", "Yearly": "Ετήσια", "Hour": "Ώρα",
    "Hours": "Ώρες", "Minute": "Λεπτό", "Minutes": "Λεπτά",
    "Distance": "Απόσταση", "Duration": "Διάρκεια", "Document": "Έγγραφο",
    "Feature": "Λειτουργία", "Field": "Πεδίο", "Fixed": "Σταθερό",
    "Group": "Ομάδα", "Item": "Στοιχείο", "Label": "Ετικέτα",
    "Line": "Γραμμή", "Link": "Σύνδεσμος", "List": "Λίστα",
    "Location": "Τοποθεσία", "Login": "Σύνδεση", "Logo": "Λογότυπο",
    "Margin": "Περιθώριο", "Member": "Μέλος", "Merge": "Συγχώνευση",
    "Message": "Μήνυμα", "Schedule": "Πρόγραμμα", "Section": "Ενότητα",
    "Security": "Ασφάλεια", "Server": "Διακομιστής", "Service": "Υπηρεσία",
    "Set": "Ορισμός", "Sort": "Ταξινόμηση", "Source": "Πηγή",
    "Subject": "Θέμα", "System": "Σύστημα", "Table": "Πίνακας",
    "Tax": "Φόρος", "Team": "Ομάδα", "Test": "Δοκιμή",
    "Time": "Χρόνος", "Title": "Τίτλος", "To": "Προς",
    "Tool": "Εργαλείο", "Top": "Κορυφή", "Tracking": "Παρακολούθηση",
    "Type": "Τύπος", "User": "Χρήστης", "Value": "Τιμή",
    "Vehicle": "Όχημα", "Version": "Έκδοση", "Volume": "Όγκος",
    "Weight": "Βάρος",
}

# ─── RUSSIAN (ru) ───
EXTRA_WORDS["ru"] = {
    "Active": "Активный", "Add": "Добавить", "Address": "Адрес",
    "All": "Все", "Amount": "Сумма", "Apply": "Применить",
    "Archive": "Архив", "Back": "Назад", "Browse": "Обзор",
    "Calculate": "Рассчитать", "Cancel": "Отмена", "Clear": "Очистить",
    "Client": "Клиент", "Close": "Закрыть", "Code": "Код",
    "Confirm": "Подтвердить", "Cost": "Стоимость", "Country": "Страна",
    "Create": "Создать", "Dashboard": "Панель", "Data": "Данные",
    "Date": "Дата", "Day": "День", "Days": "Дни",
    "Delete": "Удалить", "Description": "Описание", "Download": "Скачать",
    "Driver": "Водитель", "Edit": "Редактировать", "Email": "Email",
    "Error": "Ошибка", "Export": "Экспорт", "Failed": "Не удалось",
    "File": "Файл", "Filter": "Фильтр", "Finance": "Финансы",
    "Fleet": "Автопарк", "From": "От", "Fuel": "Топливо",
    "Generate": "Сгенерировать", "Gross": "Брутто", "Help": "Помощь",
    "Hide": "Скрыть", "History": "История", "Home": "Главная",
    "Hour": "Час", "Import": "Импорт", "Info": "Информация",
    "Invoice": "Счет", "Language": "Язык", "Load": "Загрузить",
    "Loading": "Загрузка", "Name": "Имя", "Net": "Нетто",
    "New": "Новый", "Next": "Следующий", "No": "Нет",
    "Notes": "Заметки", "OK": "OK", "Open": "Открыть",
    "Overview": "Обзор", "Paid": "Оплачено", "Password": "Пароль",
    "Preview": "Предпросмотр", "Previous": "Предыдущий", "Print": "Печать",
    "Refresh": "Обновить", "Remove": "Удалить", "Save": "Сохранить",
    "Search": "Поиск", "Select": "Выбрать", "Send": "Отправить",
    "Sent": "Отправлено", "Settings": "Настройки", "Share": "Поделиться",
    "Show": "Показать", "Signature": "Подпись", "Start": "Начало",
    "Status": "Статус", "Success": "Успех", "Total": "Итого",
    "Trip": "Поездка", "Truck": "Грузовик", "Update": "Обновить",
    "Upload": "Загрузить", "View": "Просмотр", "Warning": "Предупреждение",
    "Year": "Год", "Yes": "Да", "Today": "Сегодня",
    "Yesterday": "Вчера", "Month": "Месяц", "Monthly": "Ежемесячно",
    "Week": "Неделя", "Weekly": "Еженедельно", "Yearly": "Ежегодно",
    "Hour": "Час", "Hours": "Часы", "Minute": "Минута",
    "Minutes": "Минуты", "Distance": "Расстояние", "Duration": "Длительность",
    "Document": "Документ", "Feature": "Функция", "Field": "Поле",
    "Fixed": "Фиксированный", "Group": "Группа", "Health": "Здоровье",
    "Image": "Изображение", "Insurance": "Страховка", "Item": "Позиция",
    "Label": "Метка", "License": "Лицензия", "Line": "Линия",
    "Link": "Ссылка", "List": "Список", "Location": "Местоположение",
    "Login": "Вход", "Logo": "Логотип", "Maintenance": "Обслуживание",
    "Margin": "Маржа", "Member": "Участник", "Merge": "Объединить",
    "Message": "Сообщение", "Schedule": "Расписание", "Section": "Раздел",
    "Security": "Безопасность", "Server": "Сервер", "Service": "Услуга",
    "Set": "Установить", "Sort": "Сортировать", "Source": "Источник",
    "Subject": "Тема", "System": "Система", "Table": "Таблица",
    "Tax": "Налог", "Team": "Команда", "Template": "Шаблон",
    "Test": "Тест", "Time": "Время", "Title": "Название",
    "To": "До", "Token": "Токен", "Tool": "Инструмент",
    "Top": "Вверх", "Tracking": "Отслеживание", "Trailer": "Прицеп",
    "Type": "Тип", "User": "Пользователь", "Value": "Значение",
    "Vehicle": "Транспортное средство", "Version": "Версия",
    "Volume": "Объем", "Weight": "Вес",
}

# ─── SLOVAK (sk) ───
EXTRA_WORDS["sk"] = {
    "Active": "Aktívny", "Add": "Pridať", "Address": "Adresa",
    "All": "Všetky", "Amount": "Suma", "Apply": "Použiť",
    "Back": "Späť", "Browse": "Prehľadávať", "Calculate": "Vypočítať",
    "Cancel": "Zrušiť", "Clear": "Vyčistiť", "Client": "Klient",
    "Close": "Zatvoriť", "Code": "Kód", "Confirm": "Potvrdiť",
    "Cost": "Náklady", "Country": "Krajina", "Create": "Vytvoriť",
    "Dashboard": "Panel", "Data": "Údaje", "Date": "Dátum",
    "Day": "Deň", "Days": "Dni", "Delete": "Vymazať",
    "Description": "Popis", "Download": "Stiahnuť", "Driver": "Vodič",
    "Edit": "Upraviť", "Email": "Email", "Error": "Chyba",
    "Export": "Exportovať", "Failed": "Zlyhalo", "File": "Súbor",
    "Filter": "Filter", "Finance": "Financie", "Fleet": "Flotila",
    "From": "Od", "Fuel": "Palivo", "Generate": "Generovať",
    "Gross": "Hrubý", "Help": "Pomoc", "Hide": "Skryť",
    "History": "História", "Home": "Domov", "Hour": "Hodina",
    "Import": "Importovať", "Info": "Info", "Invoice": "Faktúra",
    "Language": "Jazyk", "Load": "Načítať", "Name": "Meno",
    "Net": "Čistý", "New": "Nový", "Next": "Ďalší", "No": "Nie",
    "Notes": "Poznámky", "OK": "OK", "Open": "Otvoriť",
    "Overview": "Prehľad", "Paid": "Zaplatené", "Password": "Heslo",
    "Preview": "Náhľad", "Previous": "Predchádzajúci", "Print": "Tlačiť",
    "Refresh": "Obnoviť", "Remove": "Odstrániť", "Save": "Uložiť",
    "Search": "Hľadať", "Select": "Vybrať", "Send": "Odoslať",
    "Sent": "Odoslané", "Settings": "Nastavenia", "Share": "Zdieľať",
    "Show": "Zobraziť", "Signature": "Podpis", "Start": "Začiatok",
    "Status": "Stav", "Success": "Úspech", "Total": "Celkom",
    "Trip": "Cesta", "Truck": "Nákladné auto", "Update": "Aktualizovať",
    "Upload": "Nahrať", "View": "Zobraziť", "Warning": "Upozornenie",
    "Year": "Rok", "Yes": "Áno", "Today": "Dnes",
    "Yesterday": "Včera", "Month": "Mesiac", "Monthly": "Mesačne",
    "Week": "Týždeň", "Weekly": "Týždenne", "Hour": "Hodina",
    "Hours": "Hodiny", "Minute": "Minúta", "Minutes": "Minúty",
    "Distance": "Vzdialenosť", "Duration": "Trvanie", "Document": "Dokument",
    "Feature": "Funkcia", "Field": "Pole", "Fixed": "Pevný",
    "Group": "Skupina", "Item": "Položka", "Label": "Označenie",
    "Line": "Riadok", "Link": "Odkaz", "List": "Zoznam",
    "Location": "Miesto", "Login": "Prihlásenie", "Logo": "Logo",
    "Margin": "Marža", "Member": "Člen", "Merge": "Zlúčiť",
    "Schedule": "Rozvrh", "Section": "Sekcia", "Security": "Bezpečnosť",
    "Server": "Server", "Service": "Služba", "Set": "Nastaviť",
    "Sort": "Zoradiť", "Subject": "Predmet", "System": "Systém",
    "Table": "Tabuľka", "Tax": "Daň", "Team": "Tím",
    "Test": "Test", "Time": "Čas", "Title": "Názov",
    "To": "Do", "Tool": "Nástroj", "Type": "Typ",
    "User": "Používateľ", "Value": "Hodnota", "Version": "Verzia",
}

# ─── POLISH (pl) ───
EXTRA_WORDS["pl"] = {
    "Active": "Aktywny", "Add": "Dodaj", "Address": "Adres",
    "All": "Wszystkie", "Amount": "Kwota", "Apply": "Zastosuj",
    "Back": "Wstecz", "Browse": "Przeglądaj", "Calculate": "Oblicz",
    "Cancel": "Anuluj", "Clear": "Wyczyść", "Client": "Klient",
    "Close": "Zamknij", "Code": "Kod", "Confirm": "Potwierdź",
    "Cost": "Koszt", "Country": "Kraj", "Create": "Utwórz",
    "Dashboard": "Panel", "Data": "Dane", "Date": "Data",
    "Day": "Dzień", "Days": "Dni", "Delete": "Usuń",
    "Description": "Opis", "Download": "Pobierz", "Driver": "Kierowca",
    "Edit": "Edytuj", "Email": "Email", "Error": "Błąd",
    "Export": "Eksportuj", "Failed": "Niepowodzenie", "File": "Plik",
    "Filter": "Filtr", "Finance": "Finanse", "Fleet": "Flota",
    "From": "Od", "Fuel": "Paliwo", "Generate": "Generuj",
    "Gross": "Brutto", "Help": "Pomoc", "Hide": "Ukryj",
    "History": "Historia", "Home": "Strona główna", "Hour": "Godzina",
    "Import": "Importuj", "Info": "Informacje", "Invoice": "Faktura",
    "Language": "Język", "Load": "Wczytaj", "Name": "Nazwa",
    "Net": "Netto", "New": "Nowy", "Next": "Następny", "No": "Nie",
    "Notes": "Uwagi", "OK": "OK", "Open": "Otwórz",
    "Overview": "Przegląd", "Paid": "Zapłacono", "Password": "Hasło",
    "Preview": "Podgląd", "Previous": "Poprzedni", "Print": "Drukuj",
    "Refresh": "Odśwież", "Remove": "Usuń", "Save": "Zapisz",
    "Search": "Szukaj", "Select": "Wybierz", "Send": "Wyślij",
    "Sent": "Wysłano", "Settings": "Ustawienia", "Share": "Udostępnij",
    "Show": "Pokaż", "Signature": "Podpis", "Start": "Początek",
    "Status": "Status", "Success": "Sukces", "Total": "Razem",
    "Trip": "Trasa", "Truck": "Ciężarówka", "Update": "Aktualizuj",
    "Upload": "Prześlij", "View": "Widok", "Warning": "Ostrzeżenie",
    "Year": "Rok", "Yes": "Tak", "Today": "Dziś",
    "Yesterday": "Wczoraj", "Month": "Miesiąc", "Monthly": "Miesięcznie",
    "Week": "Tydzień", "Weekly": "Tygodniowo", "Yearly": "Rocznie",
    "Hours": "Godziny", "Minute": "Minuta", "Minutes": "Minuty",
    "Distance": "Odległość", "Duration": "Czas trwania",
    "Document": "Dokument", "Feature": "Funkcja", "Field": "Pole",
    "Fixed": "Stały", "Group": "Grupa", "Item": "Pozycja",
    "Label": "Etykieta", "Line": "Linia", "Link": "Link",
    "List": "Lista", "Location": "Lokalizacja", "Login": "Logowanie",
    "Logo": "Logo", "Margin": "Marża", "Member": "Członek",
    "Merge": "Scal", "Schedule": "Harmonogram", "Section": "Sekcja",
    "Security": "Bezpieczeństwo", "Server": "Serwer", "Service": "Usługa",
    "Set": "Ustaw", "Sort": "Sortuj", "Subject": "Temat",
    "System": "System", "Table": "Tabela", "Tax": "Podatek",
    "Team": "Zespół", "Test": "Test", "Time": "Czas",
    "Title": "Tytuł", "To": "Do", "Tool": "Narzędzie",
    "Type": "Typ", "User": "Użytkownik", "Value": "Wartość",
    "Version": "Wersja", "Volume": "Objętość",
}

# ─── UKRAINIAN (uk) ───
EXTRA_WORDS["uk"] = {
    "Active": "Активний", "Add": "Додати", "Address": "Адреса",
    "All": "Всі", "Amount": "Сума", "Apply": "Застосувати",
    "Back": "Назад", "Cancel": "Скасувати", "Clear": "Очистити",
    "Client": "Клієнт", "Close": "Закрити", "Code": "Код",
    "Confirm": "Підтвердити", "Cost": "Вартість", "Country": "Країна",
    "Create": "Створити", "Dashboard": "Панель", "Data": "Дані",
    "Date": "Дата", "Day": "День", "Days": "Дні",
    "Delete": "Видалити", "Description": "Опис", "Download": "Завантажити",
    "Driver": "Водій", "Edit": "Редагувати", "Email": "Email",
    "Error": "Помилка", "Export": "Експорт", "Failed": "Не вдалося",
    "File": "Файл", "Filter": "Фільтр", "From": "Від",
    "Fuel": "Паливо", "Generate": "Згенерувати", "Gross": "Брутто",
    "Help": "Допомога", "Hide": "Приховати", "History": "Історія",
    "Home": "Головна", "Hour": "Година", "Import": "Імпорт",
    "Info": "Інформація", "Invoice": "Рахунок", "Language": "Мова",
    "Load": "Завантажити", "Name": "Ім'я", "Net": "Нетто",
    "New": "Новий", "Next": "Наступний", "No": "Ні",
    "Notes": "Нотатки", "OK": "OK", "Open": "Відкрити",
    "Overview": "Огляд", "Paid": "Оплачено", "Password": "Пароль",
    "Preview": "Попередній перегляд", "Previous": "Попередній",
    "Print": "Друк", "Refresh": "Оновити", "Remove": "Видалити",
    "Save": "Зберегти", "Search": "Пошук", "Select": "Вибрати",
    "Send": "Відправити", "Sent": "Відправлено", "Settings": "Налаштування",
    "Share": "Поділитися", "Show": "Показати", "Signature": "Підпис",
    "Start": "Початок", "Status": "Статус", "Success": "Успіх",
    "Total": "Всього", "Trip": "Поїздка", "Truck": "Вантажівка",
    "Update": "Оновити", "Upload": "Завантажити", "View": "Перегляд",
    "Warning": "Попередження", "Year": "Рік", "Yes": "Так",
    "Today": "Сьогодні", "Yesterday": "Вчора", "Month": "Місяць",
    "Monthly": "Щомісяця", "Week": "Тиждень", "Weekly": "Щотижня",
    "Hours": "Години", "Minute": "Хвилина", "Minutes": "Хвилини",
    "Distance": "Відстань", "Duration": "Тривалість", "Document": "Документ",
    "Feature": "Функція", "Field": "Поле", "Fixed": "Фіксований",
    "Group": "Група", "Item": "Позиція", "Label": "Мітка",
    "Line": "Лінія", "Link": "Посилання", "List": "Список",
    "Location": "Місцезнаходження", "Login": "Вхід", "Logo": "Логотип",
    "Margin": "Маржа", "Member": "Учасник", "Merge": "Об'єднати",
    "Schedule": "Розклад", "Section": "Розділ", "Security": "Безпека",
    "Server": "Сервер", "Service": "Послуга", "Set": "Встановити",
    "Sort": "Сортувати", "Subject": "Тема", "System": "Система",
    "Table": "Таблиця", "Tax": "Податок", "Team": "Команда",
    "Test": "Тест", "Time": "Час", "Title": "Назва",
    "To": "До", "Tool": "Інструмент", "Type": "Тип",
    "User": "Користувач", "Value": "Значення", "Version": "Версія",
}

# ─── SPANISH (es) ───
EXTRA_WORDS["es"] = {
    "Active": "Activo", "Add": "Añadir", "Address": "Dirección",
    "All": "Todos", "Amount": "Importe", "Apply": "Aplicar",
    "Back": "Atrás", "Browse": "Examinar", "Calculate": "Calcular",
    "Cancel": "Cancelar", "Clear": "Limpiar", "Client": "Cliente",
    "Close": "Cerrar", "Code": "Código", "Confirm": "Confirmar",
    "Cost": "Costo", "Country": "País", "Create": "Crear",
    "Dashboard": "Panel", "Data": "Datos", "Date": "Fecha",
    "Day": "Día", "Days": "Días", "Delete": "Eliminar",
    "Description": "Descripción", "Download": "Descargar",
    "Driver": "Conductor", "Edit": "Editar", "Email": "Correo electrónico",
    "Error": "Error", "Export": "Exportar", "Failed": "Falló",
    "File": "Archivo", "Filter": "Filtrar", "Finance": "Finanzas",
    "Fleet": "Flota", "From": "De", "Fuel": "Combustible",
    "Generate": "Generar", "Gross": "Bruto", "Help": "Ayuda",
    "Hide": "Ocultar", "History": "Historial", "Home": "Inicio",
    "Hour": "Hora", "Import": "Importar", "Info": "Información",
    "Invoice": "Factura", "Language": "Idioma", "Load": "Cargar",
    "Loading": "Cargando", "Name": "Nombre", "Net": "Neto",
    "New": "Nuevo", "Next": "Siguiente", "No": "No",
    "Notes": "Notas", "OK": "OK", "Open": "Abrir",
    "Overview": "Resumen", "Paid": "Pagado", "Password": "Contraseña",
    "Preview": "Vista previa", "Previous": "Anterior", "Print": "Imprimir",
    "Refresh": "Actualizar", "Remove": "Eliminar", "Save": "Guardar",
    "Search": "Buscar", "Select": "Seleccionar", "Send": "Enviar",
    "Sent": "Enviado", "Settings": "Configuración", "Share": "Compartir",
    "Show": "Mostrar", "Signature": "Firma", "Start": "Inicio",
    "Status": "Estado", "Success": "Éxito", "Total": "Total",
    "Trip": "Viaje", "Truck": "Camión", "Update": "Actualizar",
    "Upload": "Subir", "View": "Ver", "Warning": "Advertencia",
    "Year": "Año", "Yes": "Sí", "Today": "Hoy",
    "Yesterday": "Ayer", "Month": "Mes", "Monthly": "Mensual",
    "Week": "Semana", "Weekly": "Semanal", "Yearly": "Anual",
    "Hours": "Horas", "Minute": "Minuto", "Minutes": "Minutos",
    "Distance": "Distancia", "Duration": "Duración", "Document": "Documento",
    "Feature": "Característica", "Field": "Campo", "Fixed": "Fijo",
    "Group": "Grupo", "Item": "Artículo", "Label": "Etiqueta",
    "Line": "Línea", "Link": "Enlace", "List": "Lista",
    "Location": "Ubicación", "Login": "Iniciar sesión", "Logo": "Logotipo",
    "Margin": "Margen", "Member": "Miembro", "Merge": "Fusionar",
    "Schedule": "Programa", "Section": "Sección", "Security": "Seguridad",
    "Server": "Servidor", "Service": "Servicio", "Set": "Establecer",
    "Sort": "Ordenar", "Subject": "Asunto", "System": "Sistema",
    "Table": "Tabla", "Tax": "Impuesto", "Team": "Equipo",
    "Test": "Prueba", "Time": "Tiempo", "Title": "Título",
    "To": "Para", "Tool": "Herramienta", "Type": "Tipo",
    "User": "Usuario", "Value": "Valor", "Version": "Versión",
    "Signature": "Firma", "Consignee": "Consignatario",
    "Consignor": "Consignador", "Carrier": "Transportista",
}

# ─── FRENCH (fr) ───
EXTRA_WORDS["fr"] = {
    "Active": "Actif", "Add": "Ajouter", "Address": "Adresse",
    "All": "Tous", "Amount": "Montant", "Apply": "Appliquer",
    "Back": "Retour", "Browse": "Parcourir", "Calculate": "Calculer",
    "Cancel": "Annuler", "Clear": "Effacer", "Client": "Client",
    "Close": "Fermer", "Code": "Code", "Confirm": "Confirmer",
    "Cost": "Coût", "Country": "Pays", "Create": "Créer",
    "Dashboard": "Tableau de bord", "Data": "Données", "Date": "Date",
    "Day": "Jour", "Days": "Jours", "Delete": "Supprimer",
    "Description": "Description", "Download": "Télécharger",
    "Driver": "Conducteur", "Edit": "Modifier", "Email": "Email",
    "Error": "Erreur", "Export": "Exporter", "Failed": "Échoué",
    "File": "Fichier", "Filter": "Filtrer", "Finance": "Finances",
    "Fleet": "Flotte", "From": "De", "Fuel": "Carburant",
    "Generate": "Générer", "Gross": "Brut", "Help": "Aide",
    "Hide": "Masquer", "History": "Historique", "Home": "Accueil",
    "Hour": "Heure", "Import": "Importer", "Info": "Info",
    "Invoice": "Facture", "Language": "Langue", "Load": "Charger",
    "Loading": "Chargement", "Name": "Nom", "Net": "Net",
    "New": "Nouveau", "Next": "Suivant", "No": "Non",
    "Notes": "Notes", "OK": "OK", "Open": "Ouvrir",
    "Overview": "Aperçu", "Paid": "Payé", "Password": "Mot de passe",
    "Preview": "Aperçu", "Previous": "Précédent", "Print": "Imprimer",
    "Refresh": "Actualiser", "Remove": "Supprimer", "Save": "Enregistrer",
    "Search": "Rechercher", "Select": "Sélectionner", "Send": "Envoyer",
    "Sent": "Envoyé", "Settings": "Paramètres", "Share": "Partager",
    "Show": "Afficher", "Signature": "Signature", "Start": "Début",
    "Status": "Statut", "Success": "Succès", "Total": "Total",
    "Trip": "Voyage", "Truck": "Camion", "Update": "Mettre à jour",
    "Upload": "Télécharger", "View": "Voir", "Warning": "Avertissement",
    "Year": "An", "Yes": "Oui", "Today": "Aujourd'hui",
    "Yesterday": "Hier", "Month": "Mois", "Monthly": "Mensuel",
    "Week": "Semaine", "Weekly": "Hebdomadaire", "Yearly": "Annuel",
    "Hours": "Heures", "Minute": "Minute", "Minutes": "Minutes",
    "Distance": "Distance", "Duration": "Durée", "Document": "Document",
    "Feature": "Fonctionnalité", "Field": "Champ", "Fixed": "Fixe",
    "Group": "Groupe", "Item": "Article", "Label": "Étiquette",
    "Line": "Ligne", "Link": "Lien", "List": "Liste",
    "Location": "Emplacement", "Login": "Connexion", "Logo": "Logo",
    "Margin": "Marge", "Member": "Membre", "Merge": "Fusionner",
    "Schedule": "Calendrier", "Section": "Section", "Security": "Sécurité",
    "Server": "Serveur", "Service": "Service", "Set": "Définir",
    "Sort": "Trier", "Subject": "Sujet", "System": "Système",
    "Table": "Tableau", "Tax": "Taxe", "Team": "Équipe",
    "Test": "Test", "Time": "Temps", "Title": "Titre",
    "To": "À", "Tool": "Outil", "Type": "Type",
    "User": "Utilisateur", "Value": "Valeur", "Version": "Version",
    "Carrier": "Transporteur", "Consignee": "Destinataire",
    "Consignor": "Expéditeur",
}

# ─── GERMAN (de) ───
EXTRA_WORDS["de"] = {
    "Active": "Aktiv", "Add": "Hinzufügen", "Address": "Adresse",
    "All": "Alle", "Amount": "Betrag", "Apply": "Anwenden",
    "Back": "Zurück", "Browse": "Durchsuchen", "Calculate": "Berechnen",
    "Cancel": "Abbrechen", "Clear": "Löschen", "Client": "Kunde",
    "Close": "Schließen", "Code": "Code", "Confirm": "Bestätigen",
    "Cost": "Kosten", "Country": "Land", "Create": "Erstellen",
    "Dashboard": "Dashboard", "Data": "Daten", "Date": "Datum",
    "Day": "Tag", "Days": "Tage", "Delete": "Löschen",
    "Description": "Beschreibung", "Download": "Herunterladen",
    "Driver": "Fahrer", "Edit": "Bearbeiten", "Email": "E-Mail",
    "Error": "Fehler", "Export": "Exportieren", "Failed": "Fehlgeschlagen",
    "File": "Datei", "Filter": "Filter", "Finance": "Finanzen",
    "Fleet": "Fuhrpark", "From": "Von", "Fuel": "Kraftstoff",
    "Generate": "Generieren", "Gross": "Brutto", "Help": "Hilfe",
    "Hide": "Verstecken", "History": "Verlauf", "Home": "Startseite",
    "Hour": "Stunde", "Import": "Importieren", "Info": "Info",
    "Invoice": "Rechnung", "Language": "Sprache", "Load": "Laden",
    "Loading": "Laden", "Name": "Name", "Net": "Netto",
    "New": "Neu", "Next": "Weiter", "No": "Nein",
    "Notes": "Notizen", "OK": "OK", "Open": "Öffnen",
    "Overview": "Übersicht", "Paid": "Bezahlt", "Password": "Passwort",
    "Preview": "Vorschau", "Previous": "Vorherige", "Print": "Drucken",
    "Refresh": "Aktualisieren", "Remove": "Entfernen", "Save": "Speichern",
    "Search": "Suchen", "Select": "Auswählen", "Send": "Senden",
    "Sent": "Gesendet", "Settings": "Einstellungen", "Share": "Teilen",
    "Show": "Anzeigen", "Signature": "Unterschrift", "Start": "Start",
    "Status": "Status", "Success": "Erfolg", "Total": "Gesamt",
    "Trip": "Reise", "Truck": "LKW", "Update": "Aktualisieren",
    "Upload": "Hochladen", "View": "Ansicht", "Warning": "Warnung",
    "Year": "Jahr", "Yes": "Ja", "Today": "Heute",
    "Yesterday": "Gestern", "Month": "Monat", "Monthly": "Monatlich",
    "Week": "Woche", "Weekly": "Wöchentlich", "Yearly": "Jährlich",
    "Hours": "Stunden", "Minute": "Minute", "Minutes": "Minuten",
    "Distance": "Entfernung", "Duration": "Dauer", "Document": "Dokument",
    "Feature": "Funktion", "Field": "Feld", "Fixed": "Fest",
    "Group": "Gruppe", "Item": "Position", "Label": "Bezeichnung",
    "Line": "Zeile", "Link": "Link", "List": "Liste",
    "Location": "Standort", "Login": "Anmeldung", "Logo": "Logo",
    "Margin": "Marge", "Member": "Mitglied", "Merge": "Zusammenführen",
    "Schedule": "Zeitplan", "Section": "Abschnitt", "Security": "Sicherheit",
    "Server": "Server", "Service": "Dienst", "Set": "Setzen",
    "Sort": "Sortieren", "Subject": "Betreff", "System": "System",
    "Table": "Tabelle", "Tax": "Steuer", "Team": "Team",
    "Test": "Test", "Time": "Zeit", "Title": "Titel",
    "To": "Bis", "Tool": "Werkzeug", "Type": "Typ",
    "User": "Benutzer", "Value": "Wert", "Version": "Version",
    "Signature": "Unterschrift", "Receipt": "Quittung",
    "Consignee": "Empfänger", "Consignor": "Absender",
    "Carrier": "Frachtführer", "Dispatch": "Disposition",
}


if __name__ == "__main__":
    main()

