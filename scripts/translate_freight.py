#!/usr/bin/env python3
"""Translate freight exchange i18n keys to all 22 languages.

Loads English freight values from ``data/translations/en.json`` and writes
translated values into every language file. For Romanian (``ro``) the script
uses hand‑crafted translations; all other languages receive the English text
as a placeholder so that human translators can fill in the real values later.

Preserves all non‑freight keys in every language file.

Usage:
    python scripts/translate_freight.py
"""
from __future__ import annotations

import json
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATIONS_DIR = os.path.join(REPO_ROOT, "data", "translations")
EN_FILE = os.path.join(TRANSLATIONS_DIR, "en.json")

# ── Romanian (ro) translations ──────────────────────────────────────────────
# Hand‑crafted Romanian translations for every freight key.
RO_FREIGHT = {
    "title": "Bursa de Transport",
    "search": "Cauta Marfuri",
    "evaluate": "Evalueaza Marfa",
    "import": "Importa ca Transport",
    "match": {
        "subtitle": "Cele mai potrivite camioane pentru aceasta marfa",
        "score": "Scor",
        "truck_id": "Camion #{id}",
    },
    "assign": "Atribuie",
    "refresh": "Reimprospatare",
    "evaluate_again": "Evalueaza Din Nou",
    "back_to_search": "Inapoi la Cautare",
    "searching": "Se cauta...",
    "provider": {
        "timocom": "TIMOCOM",
        "trans_eu": "Trans.eu",
        "teleroute": "Teleroute",
        "wtransnet": "Wtransnet",
        "connected": "Conectat",
        "disconnected": "Deconectat",
        "error": "Eroare",
        "degraded": "Degradat",
    },
    "status": {
        "connected": "Conectat",
        "degraded": "Degradat",
        "disconnected": "Deconectat",
        "error": "Eroare",
    },
    "connection": {
        "connect": "Conecteaza",
        "disconnect": "Deconecteaza",
        "test": "Testeaza Conexiunea",
        "add_first": "Adauga Primul Furnizor",
        "client_id": "ID Client",
        "client_secret": "Secret Client",
        "client_id_placeholder": "Introduceti ID-ul client",
        "client_secret_placeholder": "Introduceti secretul client",
        "no_providers": "Niciun furnizor conectat",
        "no_providers_hint": "Conectati-va la o bursa de transport pentru a cauta marfuri",
        "test_success": "Conexiune reusita ({latency}ms)",
        "test_failed": "Conexiune esuata: {error}",
        "health_check": "Verificare Stare",
        "credentials": "Credentiale API",
        "last_checked": "Ultima verificare: {time}",
    },
    "provider_settings": {
        "title": "Furnizori Bursa de Transport",
        "subtitle": "Gestionati conexiunile la platformele de transport",
    },
    "load_detail": {
        "title": "Detalii Marfa",
    },
    "match_reason": {
        "lowest_deadhead": "Cel mai mic deadhead",
        "closest_vehicle": "Cel mai apropiat vehicul compatibil",
        "highest_profit": "Cel mai mare profit estimat",
        "driver_hours": "Soferul are ore suficiente",
        "trailer_compatible": "Tip remorca compatibil",
        "maintenance_health": "Stare buna de intretinere",
        "reliable_history": "Istoric de livrare fiabil",
        "good_positioning": "Pozitionare buna pentru viitor",
    },
    "compat": {
        "trailer_mismatch": "Tip remorca incompatibil",
        "driver_hours_insufficient": "Ore sofer insuficiente",
        "maintenance_due": "Intretinere depasita",
        "vehicle_unavailable": "Vehicul indisponibil",
        "adr_required": "Certificare ADR necesara",
    },
    "filters": {
        "title": "Filtre",
        "route": "Ruta",
        "date_range": "Interval Data",
        "vehicle": "Vehicul",
    },
    "filter": {
        "loading_place": "Loc incarcare",
        "delivery_place": "Loc descarcare",
        "date": "Interval data",
        "trailer_type": "Tip remorca",
        "adr": "ADR (periculos)",
        "weight": "Greutate",
        "price": "Pret",
        "distance": "Distanta",
        "radius": "Raza (km)",
        "all_providers": "Toti furnizorii",
        "search_now": "Cauta",
        "save_search": "Salveaza Cautarea",
        "date_from_placeholder": "De la (AAAA-LL-ZZ)",
        "date_to_placeholder": "Pana la (AAAA-LL-ZZ)",
        "missing_route": "Introduceti atat originea cat si destinatia",
        "weight_min_placeholder": "Min kg",
        "weight_max_placeholder": "Max kg",
        "distance_max_placeholder": "Max km",
        "loading_type": "Tip Incarcare",
        "loading_country_placeholder": "Tara incarcare (ex: RO)",
        "delivery_country_placeholder": "Tara descarcare (ex: DE)",
        "country": "Tari",
        "sort_by": "Sorteaza dupa",
    },
    "loading_type": {
        "any": "Orice Tip",
    },
    "trailer": {
        "any": "Oricare",
        "standard": "Standard",
        "refrigerated": "Frigorific",
        "tanker": "Cisterna",
        "flatbed": "Platforma",
        "low_loader": "Trailer Jos",
    },
    "results": {
        "empty_title": "Niciun rezultat gasit",
        "empty_subtitle": "Incercati sa ajustati criteriile de cautare",
        "count": "{count} rezultate",
        "last_updated": "Ultima actualizare: {time}",
    },
    "sort": {
        "relevance": "Relevanta",
        "price_asc": "Pret: Crescator",
        "price_desc": "Pret: Descrescator",
        "distance_asc": "Distanta: Scurt la Lung",
        "distance_desc": "Distanta: Lung la Scurt",
        "date_asc": "Data: Cele mai vechi",
        "date_desc": "Data: Cele mai noi",
    },
    "col": {
        "provider": "Furnizor",
    },
    "eval": {
        "revenue": "Venit Estimat",
        "fuel_cost": "Cost Combustibil",
        "toll_cost": "Taxe Drum",
        "driver_salary": "Salariu Sofer",
        "deadhead": "Distanta Deadhead",
        "expected_profit": "Profit Estimat",
        "profit_margin": "Marja Profit",
        "duration": "Durata Est.",
        "risk_score": "Scor Risc",
        "vehicle_compat": "Compatibilitate Vehicul",
        "driver_compat": "Compatibilitate Sofer",
        "compatible": "Compatibil",
        "not_compatible": "Incompatibil",
        "subtitle": "Evaluare financiara si analiza de risc",
        "total_cost": "Cost Total",
        "compatibility": "Compatibilitate",
    },
    "import_result": {
        "success": "Marfa importata ca transport #{trip_id}",
        "failed": "Import esuat: {error}",
        "duplicate": "Aceasta marfa a fost deja importata",
        "confirm_title": "Importa Marfa ca Transport",
        "confirm_body": "Creati un transport nou din aceasta marfa?",
        "source_label": "Sursa",
    },
    "health": {
        "healthy": "Sanatos",
        "degraded": "Degradat",
        "down": "Nefunctional",
    },
}

# ── All supported language codes ────────────────────────────────────────────
# Romanian (ro) is the only language with hand‑crafted translations.
LANGUAGES = [
    "ro", "de", "fr", "it", "es", "nl", "pl", "hu", "cs", "sk",
    "bg", "sr", "hr", "bs", "sl", "uk", "ru", "tr", "el", "pt", "sv",
]


def deep_copy_freight(src: dict) -> dict:
    """Deep‑copy the freight section so mutations do not affect the source."""
    import copy
    return copy.deepcopy(src)


def main() -> None:
    # 1. Load English translations to get the freight structure
    if not os.path.isfile(EN_FILE):
        logger.error("English translation file not found: %s", EN_FILE)
        sys.exit(1)

    with open(EN_FILE, encoding="utf-8") as f:
        en_data = json.load(f)

    en_freight = en_data.get("freight", {})
    if not en_freight:
        logger.error("No 'freight' key found in en.json")
        sys.exit(1)

    logger.info("Loaded English freight section with %d top-level keys", len(en_freight))

    # 2. Process every language
    for lang in LANGUAGES:
        lang_file = os.path.join(TRANSLATIONS_DIR, f"{lang}.json")

        if not os.path.isfile(lang_file):
            logger.warning("Language file not found, skipping: %s", lang_file)
            continue

        with open(lang_file, encoding="utf-8") as f:
            lang_data = json.load(f)

        # Build the freight section for this language
        if lang == "ro":
            # Use hand‑crafted Romanian translations
            freight_section = deep_copy_freight(RO_FREIGHT)
            logger.info("  [ro] Using hand‑crafted Romanian translations")
        else:
            # Use English as placeholder (preserves structure for translators)
            freight_section = deep_copy_freight(en_freight)
            logger.info("  [%s] Copied English as placeholder", lang)

        # Update the language data — preserves all non‑freight keys
        lang_data["freight"] = freight_section

        with open(lang_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(lang_data, f, ensure_ascii=False, indent=2)
            f.write("\n")

        logger.info("  ✓ Updated %s", lang_file)

    logger.info("\nDone — all language files updated.")


if __name__ == "__main__":
    main()
