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
from typing import Any

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
    "doc_id": [
        r"\b([A-Z]{2,6}[-_.\s]?\d{3,8})\b",
        r"\b(\d{4,}[-/][A-Z]{2,6}\d{0,4})\b",
        r"\b([A-Z]{2,4}\d{4,8})\b",
    ],
}


def _compile_patterns() -> dict[str, list[re.Pattern]]:
    return {
        key: [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in patterns]
        for key, patterns in EXTRACTION_PATTERNS.items()
    }


_COMPILED = _compile_patterns()


# ── Keyword markers that typically precede a document ID ────────────
_DOC_ID_KEYWORDS = [
    r"CMR", r"No\.", r"Nr\.", r"Number", r"N[°o]\.?",
    r"Invoice", r"Factura", r"Facture", r"Rechnung",
    r"Document", r"Ref\.", r"Reference", r"Referință",
    r"Contract", r"Ordin", r"Comandă",
]

# ── Proximity window (chars) around a keyword to search for doc ID ─
_DOC_ID_PROXIMITY = 80


def _extract_doc_id(text: str) -> str:
    """Extract a document ID with keyword-proximity priority.

    Searches for ID patterns near known document-ID keywords first;
    falls back to the first generic ID pattern found anywhere in text.
    """
    for kw in _DOC_ID_KEYWORDS:
        kw_rx = re.compile(kw, re.IGNORECASE)
        for kw_match in kw_rx.finditer(text):
            start = max(0, kw_match.start() - _DOC_ID_PROXIMITY)
            end = min(len(text), kw_match.end() + _DOC_ID_PROXIMITY)
            window = text[start:end]
            for rx_str in EXTRACTION_PATTERNS["doc_id"]:
                rx = re.compile(rx_str, re.IGNORECASE | re.MULTILINE)
                m = rx.search(window)
                if m:
                    return _strip(m.group(1))
    # Fallback: search entire text with generic patterns
    for rx_str in EXTRACTION_PATTERNS["doc_id"]:
        rx = re.compile(rx_str, re.IGNORECASE | re.MULTILINE)
        m = rx.search(text)
        if m:
            return _strip(m.group(1))
    return ""


def _strip(value: str) -> str:
    value = value.strip(" \t\r\n.,;:-")
    # Normalize internal whitespace runs (including newlines) to a single space
    # so that multi-line captures don't carry unwanted formatting.
    return re.sub(r"\s+", " ", value)


def extract_fields(text: str, user_company: str = "") -> dict[str, str]:
    """Return a dict of ``{field: value}`` for every pattern that matches.

    Values that match the *user_company* string (the logged-in transport
    company) are stripped out of stamp fields to avoid false-positive
    client matches against the user's own company.

    ``doc_id`` is handled separately with keyword-proximity priority so
    that IDs near CMR/invoice/document-number keywords are preferred.
    """
    out: dict[str, str] = {}
    for key, regexes in _COMPILED.items():
        if key == "doc_id":
            continue  # handled below with keyword proximity
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

    # doc_id uses keyword-proximity priority, then falls back to
    # the generic patterns registered in EXTRACTION_PATTERNS["doc_id"].
    doc_id = _extract_doc_id(text)
    if doc_id:
        out["doc_id"] = doc_id

    return out


def find_first(text: str, regex_list: list[str]) -> str:
    """Convenience helper — return the first capture of any regex in
    ``regex_list`` or empty string."""
    for rx_str in regex_list:
        m = re.search(rx_str, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return _strip(m.group(1))
    return ""


def collect_client_name_candidates(extracted: dict[str, str]) -> list[str]:
    """Return a deduplicated, stripped list of company names extracted from
    OCR fields that could represent a client (consignor, consignee, stamps).

    The caller (typically the pipeline) cross-references these against
    the ClientRepository to find the actual client.
    """
    seen: set[str] = set()
    candidates: list[str] = []
    for key in ("consignor", "consignee", "consignor_stamp", "consignee_stamp", "haulier_stamp"):
        val = extracted.get(key, "")
        val = val.strip()
        if val and val.lower() not in seen:
            seen.add(val.lower())
            candidates.append(val)
    return candidates


def match_clients_from_extracted(
    extracted: dict[str, str],
    client_repo: Any,
) -> list[str]:
    """Cross-reference extracted company names against the client repository
    (fuzzy LIKE match).  Returns a sorted list of matched client names.

    Every extracted field is checked against the client DB via
    ``ClientRepository.search_by_name``.
    """
    if not hasattr(client_repo, "search_by_name"):
        return []
    candidates = collect_client_name_candidates(extracted)
    matched: set[str] = set()
    for name in candidates:
        try:
            rows = client_repo.search_by_name(name, fuzzy=True, limit=3)
        except Exception:
            continue
        for row in rows:
            client_name = (row.get("name") or "").strip()
            if client_name:
                matched.add(client_name)
    return sorted(matched)


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
    # Fuzzy-fallback via dateutil parser for non-standard formats.
    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(s, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    logger.warning("normalize_date: unable to parse '%s'", date_str)
    return ""
