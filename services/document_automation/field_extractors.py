"""Heuristics that pull structured fields out of raw OCR text.

Used by :class:`OcrExtractor` after Tesseract / cloud OCR has produced
plain text.  Each helper returns ``None`` (no match) or a string.

The patterns are deliberately permissive — exact numbers in real
logistics documents (CMR, invoice) vary wildly between countries and
companies, so the regexes err on the side of catching too much and
rely on the trip-match step to disambiguate.

Field validation helpers (:func:`validate_field`, :func:`validate_extracted_fields`)
provide format and confidence checks on extracted values.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from models.common import ErrorDetail

from .types import FieldValidationResult

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


# ── Field validation patterns ─────────────────────────────────────────
# Used by :func:`validate_field` to check extracted values match
# expected formats for common logistics document fields.

FIELD_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    # Invoice number: prefix + digits, e.g. INV-12345, FV/2024/001
    "invoice_number": re.compile(
        r"^[A-Z]{0,6}[\-/_]?\d[\d\-/_]{2,20}$", re.IGNORECASE
    ),
    # CMR number: letters + digits, e.g. CMR-12345, 12AB3456
    "cmr_number": re.compile(
        r"^[A-Z0-9][A-Z0-9\-/\s]{3,20}$", re.IGNORECASE
    ),
    # Document number (generic): at least 3 chars with digits
    "doc_id": re.compile(
        r"^[A-Z0-9][A-Z0-9\-/._\s]{2,20}$", re.IGNORECASE
    ),
    # Date: YYYY-MM-DD, DD/MM/YYYY, etc.
    "date": re.compile(
        r"^\d{2,4}[./\-]\d{1,2}[./\-]\d{2,4}$"
    ),
    # Amount: positive number with optional 2 decimal places
    "amount": re.compile(
        r"^\d+(?:[.,]\d{1,2})?$"
    ),
    # Truck plate: 1-3 letters + 2-4 digits + optional 1-3 letters
    "truck_plate": re.compile(
        r"^[A-Za-z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3}$"
    ),
    "trailer_plate": re.compile(
        r"^[A-Za-z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Za-z0-9]{1,3}$"
    ),
    # Weight (kg): up to 7 digits with optional decimal
    "weight_kg": re.compile(
        r"^\d{1,7}(?:[.,]\d+)?$"
    ),
    # Package count: 1-5 digits
    "package_count": re.compile(
        r"^\d{1,5}$"
    ),
}


def validate_field(key: str, value: str) -> tuple[float, str]:
    """Validate a single extracted field against its expected format.

    Args:
        key: Field name (e.g. ``"invoice_number"``, ``"date"``).
        value: Extracted string value.

    Returns:
        Tuple of ``(confidence, warning_or_empty)`` where *confidence* is
        a float in [0.0, 1.0] and *warning* is a human-readable message
        (empty string when the value passes all checks).

    Fields without an explicit pattern in :data:`FIELD_FORMAT_PATTERNS`
    are accepted with a default confidence of 0.5 (uncertain).
    """
    if not value or not value.strip():
        return 0.0, "Field value is empty"

    value = value.strip()

    # ── Specific format checks ────────────────────────────────────────
    pattern = FIELD_FORMAT_PATTERNS.get(key)
    if pattern is not None:
        if pattern.match(value):
            return 1.0, ""
        return 0.3, f"'{key}' value '{value}' does not match expected format"

    # ── Amount-specific numeric checks ────────────────────────────────
    if key == "amount":
        try:
            amt = float(value.replace(",", "."))
            if amt <= 0:
                return 0.0, "Amount must be positive"
            # Check for 2 decimal places
            if "." in value:
                _, decimals = value.split(".")
                if len(decimals) > 2:
                    return 0.5, "Amount has more than 2 decimal places"
            return 1.0, ""
        except ValueError:
            return 0.0, f"Amount '{value}' is not a valid number"

    # ── Date-specific parsing ─────────────────────────────────────────
    if key == "date":
        normalized = normalize_date(value)
        if normalized:
            return 1.0, ""
        return 0.2, f"Date '{value}' could not be parsed"

    # ── Client name (no strong format — accept with moderate conf) ────
    if key in ("client_name", "consignee", "consignor",
               "consignee_stamp", "consignor_stamp", "haulier_stamp"):
        if len(value) < 2:
            return 0.2, f"'{key}' value too short ({len(value)} chars)"
        if not re.search(r"[A-Za-z]", value):
            return 0.4, f"'{key}' contains no alphabetic characters"
        return 0.8, ""  # plausible company name

    # ── Unknown field — accept with moderate confidence ───────────────
    if len(value) < 2:
        return 0.3, f"'{key}' value too short ({len(value)} chars)"
    return 0.5, ""


def validate_extracted_fields(
    extracted: dict[str, str],
    *,
    client_names: list[str] | None = None,
) -> FieldValidationResult:
    """Validate all extracted fields and return a structured result.

    Each field is checked against format patterns.  When a list of known
    *client_names* is provided, ``client_name`` fields are cross-referenced
    with fuzzy matching.

    Returns:
        A :class:`FieldValidationResult` with per-field confidence scores,
        errors for critical failures, and warnings for low-confidence values.
    """
    errors: list[str] = []
    warnings: list[str] = []
    field_scores: dict[str, float] = {}
    total_score = 0.0
    field_count = 0

    for key, value in extracted.items():
        if key in ("raw_text", "doc_type", "engine") or not value:
            continue
        score, warning = validate_field(key, value)
        field_scores[key] = score
        field_count += 1
        total_score += score

        if score == 0.0:
            errors.append(f"{key}: {warning}" if warning else f"{key}: invalid value")
        elif score < 0.6 and warning:
            warnings.append(f"{key}: {warning}")

    # ── Client name cross-reference ───────────────────────────────────
    client_keys = ("client_name", "consignee", "consignor",
                   "consignee_stamp", "consignor_stamp", "haulier_stamp")
    if client_names:
        for ck in client_keys:
            cv = extracted.get(ck, "")
            if cv and cv.strip().lower() not in {n.strip().lower() for n in client_names}:
                warnings.append(
                    f"{ck}: '{cv}' does not match any known client"
                )
                field_scores[ck] = min(field_scores.get(ck, 1.0), 0.5)

    # ── Overall score ─────────────────────────────────────────────────
    overall = total_score / max(field_count, 1)
    passed = overall >= 0.6 and len(errors) == 0

    if not field_count:
        errors.append("No extractable fields found")

    return FieldValidationResult(
        passed=passed,
        score=round(overall, 3),
        errors=errors,
        warnings=warnings,
        field_scores=field_scores,
    )


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
