"""Heuristics that pull structured fields out of raw OCR text.

Used by :class:`OcrExtractor` after Tesseract / cloud OCR has produced
plain text.  Each helper returns ``None`` (no match) or a string.

The patterns are deliberately permissive — exact numbers in real
logistics documents (CMR, invoice) vary wildly between countries and
companies, so the regexes err on the side of catching too much and
rely on the trip-match step to disambiguate.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

logger = logging.getLogger("document_automation.field_extractors")

# Each entry is a list of regexes tried in order; first match wins.
EXTRACTION_PATTERNS: dict[str, list[str]] = {
    "cmr_number": [
        r"CMR[\s\-]?(?:N[ro°\.]?|No\.?|Nr\.?|Number)?[\s.:]*([A-Z0-9][A-Z0-9\-/\s]{3,20})",
        r"\bCMR[\s\-]([A-Z0-9][A-Z0-9\-/\s]{3,20})\b",
        r"(?<!\w)([A-Z]{2}\s?\d{4,10}(?:\s?[A-Z0-9]{1,5})?)(?!\w)",
    ],
    "invoice_number": [
        r"(?:Invoice|Factura|Facture|Rechnung|Seria)\s*(?:Nr|No|Number|N°|Nummer|Nr\.)?[\s.:]*([A-Z]{0,3}[\-/]?\d[\w\-/]{2,20})",
        r"\bINV[\-_]?(\d{3,12})\b",
        r"(?:Nr\.|No\.)\s*([A-Z]{1,3}[\-/]?\d{2,12})\b",
    ],
    "truck_plate": [
        r"(?:Tractor|Truck|Vehicle|Camion|LKW|Truck\s*plate|Vehicle\s*reg\.?|Tractor\s*plate|Nr\.?\s*[îi]nmatriculare|Autovehicul|Cap\s*tractor|Rendsz[aá]m|Rejestracja|Pojazd)\s*[:\-]?\s*([A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3})",
        r"(?<!\w)([A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3})(?!\w)",
    ],
    "trailer_plate": [
        r"(?:Trailer|Anh[aä]nger|Remorque|Semi\s*trailer|Remorc[aă]|Pótrépsy|Naczepa)\s*[:\-]?\s*([A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3})",
        r"(?<!\w)([A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3})(?!\w)",
    ],
    "date": [
        r"\b(\d{4}[./\-]\d{1,2}[./\-]\d{1,2})\b",
        r"\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\b",
    ],
    "weight_kg": [
        r"(?:Gross\s*weight|Peso\s*lordo|Brutto(?:gewicht)?|Masse\s*brute)\s*[:\-]?\s*(\d{1,7}(?:[.,]\d+)?)\s*(?:kg|KG|Kilos?)?",
    ],
    "package_count": [
        r"(?:Number\s*of\s*packages?|Packages?|Colli|Colis|Paquets?|Anzahl\s*Packst(?:ü|u)cke)\s*[:\-]?\s*(\d{1,5})",
    ],
    "volume_m3": [
        r"(?:Volume|Volumen)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(?:m3|m³|cbm)",
    ],
    "loading_place": [
        r"(?:Place\s*of\s*(?:taking\s*over|loading)|Lieu\s*de\s*chargement|Ladeort|Luogo\s*di\s*carico)\s*[:\-]?\s*([A-Z][\w\s.,\-/]{2,80})",
    ],
    "delivery_place": [
        r"(?:Place\s*of\s*delivery|Destination|Lieferort|Lieu\s*de\s*livraison|Luogo\s*di\s*consegna)\s*[:\-]?\s*([A-Z][\w\s.,\-/]{2,80})",
    ],
    "consignee": [
        r"(?:Consignee|Empf[aä]nger|Destinatario|Destinataire|Destinatar|C[t]itor)\s*[:\-]?\s*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
    ],
    "consignor": [
        r"(?:Consignor|Shipper|Absender|Speditore|Esp[ée]diteur|Expeditor|Felad[uú])\s*[:\-]?\s*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
    ],
    "driver_name": [
        r"(?:Driver\s*name|Fahrer|Conducteur|Autista|\u0218ofer|Conduc\u0103tor|Vezet\u0151|Kierowca|\u0412\u043e\u0434\u0430\u0447)\s*[:\-]?\s*([A-Za-z\u00C0-\u017F\u0400-\u04FF][a-zA-Z\u00C0-\u017F\u0400-\u04FF'\-]{1,40}(?:\s+[A-Za-z\u00C0-\u017F\u0400-\u04FF][a-zA-Z\u00C0-\u017F\u0400-\u04FF'\-]{1,40}){0,3})",
    ],
    "consignor_stamp": [
        r"(?:1[\.)]\s*).*?(?:Name|Nume|Denumirea)[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
        r"Stamp\s*1[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
    ],
    "consignee_stamp": [
        r"(?:2[\.)]\s*).*?(?:Name|Nume|Denumirea)[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
        r"Stamp\s*2[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
    ],
    "haulier_stamp": [
        r"(?:16[\.)]\s*).*?(?:Name|Nume|Denumirea|Carrier|Haulier|Transport)[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
        r"Stamp\s*16[:\s]*([A-Za-z\u00C0-\u017F][\w\s.,\-/&]{2,80})",
    ],
}


def _compile_patterns() -> dict[str, list[re.Pattern]]:
    return {
        key: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        for key, patterns in EXTRACTION_PATTERNS.items()
    }


_COMPILED = _compile_patterns()


def _strip(value: str) -> str:
    return value.strip(" \t\r\n.,;:-")


def extract_fields(text: str, user_company: str = "") -> dict[str, str]:
    """Return a dict of ``{field: value}`` for every pattern that matches.

    Values that match the *user_company* string (the logged-in transport
    company) are stripped out of stamp fields to avoid false-positive
    client matches against the user's own company.
    """
    out: dict[str, str] = {}
    for key, regexes in _COMPILED.items():
        for rx in regexes:
            m = rx.search(text)
            if m:
                out[key] = _strip(m.group(1))
                break

    # Filter the user's own company out of stamp fields.
    uc = user_company.strip().lower() if user_company else ""
    if uc:
        for sk in ("consignor_stamp", "consignee_stamp", "haulier_stamp"):
            val = out.get(sk)
            if val and val.strip().lower() == uc:
                del out[sk]
    return out


def find_first(text: str, regex_list: list[str]) -> str:
    """Convenience helper — return the first capture of any regex in
    ``regex_list`` or empty string."""
    for rx_str in regex_list:
        m = re.search(rx_str, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return _strip(m.group(1))
    return ""


# Fuzzy matching of free-form text against known client / driver names
# is performed by the trip-matcher step (which has access to the DB).
# These helpers are kept simple on purpose.
def normalize_plate(plate: str) -> str:
    """Uppercase and strip whitespace / dashes from a license plate."""
    return re.sub(r"[\s\-]", "", (plate or "").upper())


def normalize_date(date_str: str) -> str:
    """Best-effort normalisation of OCR date strings to ``YYYY-MM-DD``.

    Returns empty string if the date can't be parsed.
    """
    s = (date_str or "").strip()
    for fmt in (
        "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
        "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d/%m/%y", "%d-%m-%y",
    ):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    logger.warning("normalize_date: unable to parse '%s'", date_str)
    return ""
