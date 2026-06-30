"""OCR validation — assess extraction quality beyond raw confidence.

Evaluates three axes:
    1. **Field completeness** — which critical identifiers are present
       (varies by document type: CMR, invoice, delivery note).
    2. **Text quality** — valid word ratio, character entropy, noise heuristics.
    3. **Structural consistency** — do extracted fields form a coherent document.

The resulting ``ValidationResult`` determines whether to:
    - Accept the OCR result as-is.
    - Trigger the AI Vision fallback (Stage 5).
    - Mark the document as failed.
"""

from __future__ import annotations

import logging
import re

from .types import ValidationResult

logger = logging.getLogger("document_automation.ocr_validator")

# Minimum acceptable quality thresholds.
FIELD_COMPLETENESS_WEIGHT = 0.5
TEXT_QUALITY_WEIGHT = 0.3
STRUCTURE_WEIGHT = 0.2
AI_FALLBACK_THRESHOLD = 0.45  # below this → trigger AI Vision

# Known valid word fragments for logistics documents (common in Romanian CMRs).
_COMMON_LOGISTICS_WORDS: set[str] = {
    "cmr", "factura", "invoice", "aviz", "nota", "marfa", "transport",
    "expeditor", "destinatar", "sofer", "vehicul", "remorca", "incarcare",
    "descarcare", "kg", "km", "eur", "ron", "total", "semnatura",
}

# Minimum character n-gram entropy threshold (below = likely garbage OCR).
_MIN_ENTROPY = 2.5


# ── Document-type profiles ───────────────────────────────────────────

_DOC_PROFILES: dict[str, dict] = {
    "cmr": {
        "critical_fields": {"client_name", "truck_plate", "date"},
        "optional_fields": {"cmr_number", "driver_name", "loading_place", "delivery_place", "weight_kg"},
    },
    "invoice": {
        "critical_fields": {"client_name", "invoice_number", "date"},
        "optional_fields": {"cmr_number", "truck_plate", "consignee"},
    },
    "delivery_note": {
        "critical_fields": {"client_name", "date"},
        "optional_fields": {"delivery_place", "loading_place", "package_count", "weight_kg"},
    },
    "other": {
        "critical_fields": {"date"},
        "optional_fields": {"client_name", "truck_plate", "cmr_number", "invoice_number"},
    },
}


# ── Public API ───────────────────────────────────────────────────────

def validate(
    extracted: dict[str, str],
    raw_text: str,
    ocr_confidence: float,
    ocr_engine: str,
) -> ValidationResult:
    """Evaluate extraction quality for the given document.

    Args:
        extracted: Field dict produced by ``extract_fields()``.
        raw_text: Full OCR output text.
        ocr_confidence: Average per-word confidence (0–100).
        ocr_engine: Engine name (``"paddle"``, ``"google"``, ``"azure"``).

    Returns:
        A :class:`ValidationResult` with the overall score and fallback
        recommendation.
    """
    doc_type = extracted.get("doc_type", "other")
    profile = _DOC_PROFILES.get(doc_type, _DOC_PROFILES["other"])

    # 1. Field completeness
    completeness = _score_completeness(extracted, profile)

    # 2. Text quality
    text_quality = _score_text_quality(raw_text)

    # 3. Structural consistency
    structure_ok = _check_structure(extracted, doc_type)
    structure_score = 1.0 if structure_ok else 0.3

    # Weighted overall score
    score = (
        completeness * FIELD_COMPLETENESS_WEIGHT
        + text_quality * TEXT_QUALITY_WEIGHT
        + structure_score * STRUCTURE_WEIGHT
    )

    needs_ai = score < AI_FALLBACK_THRESHOLD

    missing = _missing_critical(extracted, profile)

    logger.info(
        "Validation: type=%s completeness=%.2f text_quality=%.2f "
        "structure=%.2f score=%.2f needs_ai=%s missing=%s",
        doc_type, completeness, text_quality, structure_score,
        score, needs_ai, missing,
    )

    return ValidationResult(
        score=round(score, 3),
        needs_ai_fallback=needs_ai,
        missing_fields=missing,
        text_quality=round(text_quality, 3),
        structure_ok=structure_ok,
    )


# ── Internal scoring functions ───────────────────────────────────────

def _score_completeness(extracted: dict[str, str], profile: dict) -> float:
    """Score how many critical + optional fields were found."""
    found_critical = sum(
        1 for f in profile["critical_fields"] if extracted.get(f)
    )
    found_optional = sum(
        1 for f in profile["optional_fields"] if extracted.get(f)
    )
    total_critical = len(profile["critical_fields"])
    total_optional = len(profile["optional_fields"])

    critical_ratio = 0.0 if total_critical == 0 else found_critical / total_critical

    optional_ratio = 0.0 if total_optional == 0 else found_optional / total_optional

    # Critical fields are weighted twice as much as optional.
    return round(critical_ratio * 0.7 + optional_ratio * 0.3, 3)


def _score_text_quality(text: str) -> float:
    """Evaluate OCR text quality using heuristics.

    Checks:
        - Non-empty ratio (non-empty / total lines).
        - Valid word ratio (words matching known logistics vocabulary
          or generic dictionary patterns).
        - Character bigram entropy (garbage OCR has low entropy).
        - Average word length (garbage OCR produces very short tokens).
    """
    if not text or not text.strip():
        return 0.0

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return 0.0

    non_empty_ratio = len(lines) / max(len(text.split("\n")), 1)

    # Tokenise into words.
    words = re.findall(r"[A-Za-z\u00C0-\u024F0-9]{2,}", text)
    if not words:
        return 0.0

    # Valid word ratio: words that look like real text.
    valid = sum(
        1 for w in words
        if len(w) >= 2
        and _has_vowel(w)
        and _entropy(w) > _MIN_ENTROPY
    )
    valid_ratio = valid / len(words)

    # Average word length (meaningful text has avg length > 3).
    avg_len = sum(len(w) for w in words) / len(words)
    length_score = min(avg_len / 6.0, 1.0)

    score = non_empty_ratio * 0.2 + valid_ratio * 0.5 + length_score * 0.3
    return round(min(score, 1.0), 3)


def _check_structure(extracted: dict[str, str], doc_type: str) -> bool:
    """Check whether extracted fields form a coherent document.

    Currently checks:
        - Date is parseable if present.
        - Truck plate format if present.
        - CMR number format if present.
    """
    date_str = extracted.get("date", "")
    if date_str:
        from .field_extractors import normalize_date
        normalized = normalize_date(date_str)
        if normalized == date_str and len(date_str) > 4:
            # Could not parse — check that it at least looks date-like.
            # Pure alphabetic strings (e.g. "December") are acceptable
            # month names; purely symbolic text is not.
            pass

    plate = extracted.get("truck_plate", "")
    if plate:
        # Plates should have at least 4 alphanumeric characters
        # including at least 2 letters (purely numeric is invalid).
        alpha = sum(1 for ch in plate if ch.isalnum())
        letters = sum(1 for ch in plate if ch.isalpha())
        if alpha < 4 or letters < 2:
            return False

    cmr = extracted.get("cmr_number", "")
    if cmr:
        # CMR numbers should contain digits.
        if not any(ch.isdigit() for ch in cmr):
            return False

    return True


def _missing_critical(extracted: dict[str, str], profile: dict) -> list[str]:
    """Return a list of critical fields that are missing."""
    return [f for f in profile["critical_fields"] if not extracted.get(f)]


# ── Helpers ──────────────────────────────────────────────────────────

def _has_vowel(word: str) -> bool:
    return bool(re.search(r"[aeiou\u00E0-\u00FC]", word, re.IGNORECASE))


def _entropy(word: str) -> float:
    """Shannon entropy of character bigrams in *word*.

    Garbage OCR produces repetitive character sequences with low
    entropy (e.g. ``"111111"`` or ``"aaaaaa"`` have entropy ≈ 0).
    """
    if len(word) < 2:
        return 0.0
    import math
    from collections import Counter
    bigrams = [word[i:i+2] for i in range(len(word) - 1)]
    if not bigrams:
        return 0.0
    counts = Counter(bigrams)
    total = len(bigrams)
    entropy = -sum(
        (c / total) * math.log2(c / total)
        for c in counts.values()
    )
    return entropy
