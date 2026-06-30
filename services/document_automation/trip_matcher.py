"""Trip matching engine.

Given a dictionary of OCR-extracted fields (and the OCR text + source
filename), score every candidate trip against those fields and return
a ranked :class:`MatchResult`.

The algorithm is a weighted multi-signal vote:

    signal                          weight
    ---------------------------------------------------
    exact CMR number match           0.10
    exact invoice number match       0.10
    client name (fuzzy) match        0.25
    truck / trailer plate match      0.20
    driver name (fuzzy) match        0.15
    date proximity                  0.10
    geographic proximity             0.15
    company stamp (fuzzy) match      0.25
    filename hint                   0.05
    ---------------------------------------------------
    maximum possible score           ~1.35 (clamped to 1.0)

Thresholds:
    confidence >= 0.95  →  auto_attach  (UI does not ask)
    0.70 <= c < 0.95     →  suggest     (UI shows top 5 candidates)
    c < 0.70            →  manual      (UI shows search dialog)
"""

from __future__ import annotations

import contextlib
import difflib
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any

from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.trip_repository import TripRepository

from .field_extractors import normalize_date, normalize_plate
from .types import MatchCandidate, MatchResult

logger = logging.getLogger("document_automation.trip_matcher")

# Default signal weights (can be overridden via settings DB).
_DEFAULT_WEIGHTS = {
    "cmr": 0.10, "invoice": 0.10, "client": 0.25, "plate": 0.20,
    "driver": 0.15, "date": 0.10, "filename": 0.05, "geographic": 0.15,
    "company_stamp": 0.25,
}
_WEIGHTS_CACHE: dict[str, float] = {}
_WEIGHTS_TS: float = 0
_WEIGHTS_TTL = 60  # seconds
_WEIGHTS_LOCK = threading.Lock()

# Cached auto-link threshold (separate from weights because it's a
# policy threshold, not a signal weight).
_AUTO_LINK_THRESHOLD_CACHE: float = 0.50
_AUTO_LINK_THRESHOLD_TS: float = 0
_AUTO_LINK_THRESHOLD_TTL = 60  # seconds
_AUTO_LINK_THRESHOLD_LOCK = threading.Lock()

# Document-type-aware signal multipliers.
# Applied on top of base weights during final scoring.
# Keys match the ``doc_type`` value from ``extract_fields()``.
_DOC_TYPE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "cmr": {
        "plate": 1.2,          # vehicle plate is critical for CMRs
        "driver": 1.5,         # driver name is very important
        "date": 1.2,           # date matters for trip identification
        "geographic": 1.2,     # loading/delivery locations key for CMRs
        "company_stamp": 1.3,  # stamp company names are primary identifiers
    },
    "invoice": {
        "invoice": 1.3,        # invoice number is the primary identifier
        "client": 1.2,         # client name is critical
    },
    "delivery_note": {
        "date": 1.4,           # delivery date is the strongest signal
        "geographic": 1.3,     # delivery location is key
    },
}


def _fuzzy_score(a: str, b: str) -> float:
    """Return a 0..1 similarity using SequenceMatcher."""
    if not a or not b:
        return 0.0
    a_l = a.lower().strip()
    b_l = b.lower().strip()
    if not a_l or not b_l:
        return 0.0
    if a_l == b_l:
        return 1.0
    return difflib.SequenceMatcher(None, a_l, b_l).ratio()


def _filename_hints(filename: str) -> dict[str, str]:
    """Pull plausible trip ID, client name, date, or plate out of a filename."""
    base = os.path.splitext(os.path.basename(filename or ""))[0]
    # Strip common prefixes like "WhatsApp Image 2024-01-15 at 12.34.56"
    cleaned = re.sub(r"(?i)^(whatsapp\s*image|scan|IMG|image|photo)\s*", "", base)
    # Replace separators with spaces
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    cleaned = re.sub(r"\.+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    hints: dict[str, str] = {"text": cleaned}

    # Try to find a trip ID — support Romanian document labels.
    # Patterns: trip-2487, #2487, CMR-2487, Factura 2487, Aviz 2487, etc.
    m = re.search(
        r"(?:(?:trip|cmr|factura|aviz|nota|cursa|comanda)[_\-\s]?|#)(\d{1,8})",
        cleaned, re.IGNORECASE,
    )
    if m:
        hints["trip_id_hint"] = m.group(1)

    # Try to find an ISO date (YYYY-MM-DD or DD.MM.YYYY) — used for
    # date proximity matching.
    m = re.search(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b", cleaned)
    if m:
        hints["date_hint"] = m.group(1)
    else:
        m = re.search(r"\b(\d{1,2}[./]\d{1,2}[./]\d{2,4})\b", cleaned)
        if m:
            hints["date_hint"] = m.group(1)

    # Try to find a plate (use cleaned text so separators are spaces)
    m = re.search(r"([A-Z]{1,3}[\s\-]?\d{2,4}[\s\-]?[A-Z]{1,3})", cleaned, re.IGNORECASE)
    if m:
        hints["plate_hint"] = normalize_plate(m.group(1))
    return hints


def _geo_fuzzy_score(ocr_place: str, trip_place: str) -> float:
    """Score geographic similarity between two place names.

    Uses token-based fuzzy matching (handles word reordering and minor
    spelling differences) rather than character-level difflib, which
    is more appropriate for placenames like "Munich, DE" vs "München".
    """
    if not ocr_place or not trip_place:
        return 0.0
    a = re.sub(r"[^\w\s]", "", ocr_place.lower())
    b = re.sub(r"[^\w\s]", "", trip_place.lower())
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    # Jaccard-like score weighted by token count.
    return len(intersection) / max(len(tokens_a), len(tokens_b))


def _load_weights(db) -> dict[str, float]:
    """Load signal weights from the settings DB, with a short TTL cache."""
    global _WEIGHTS_CACHE, _WEIGHTS_TS
    now = time.time()
    with _WEIGHTS_LOCK:
        if _WEIGHTS_CACHE and (now - _WEIGHTS_TS) < _WEIGHTS_TTL:
            return _WEIGHTS_CACHE
    w = dict(_DEFAULT_WEIGHTS)
    try:
        rows = db.conn.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'match_weight_%'"
        ).fetchall()
        for r in rows:
            key = r["key"].replace("match_weight_", "")
            with contextlib.suppress(ValueError, TypeError):
                w[key] = float(r["value"])
    except Exception:
        pass
    with _WEIGHTS_LOCK:
        _WEIGHTS_CACHE = w
        _WEIGHTS_TS = now
    return w


def _load_auto_link_threshold(db) -> float:
    """Load ``auto_link_threshold`` from the settings DB with a short TTL cache.

    Returns the threshold (0..1) — the minimum confidence score at which
    a document uploaded to the Document Center will be automatically
    linked to its matched trip.  Default: 0.50.
    """
    global _AUTO_LINK_THRESHOLD_CACHE, _AUTO_LINK_THRESHOLD_TS
    now = time.time()
    with _AUTO_LINK_THRESHOLD_LOCK:
        if (now - _AUTO_LINK_THRESHOLD_TS) < _AUTO_LINK_THRESHOLD_TTL:
            return _AUTO_LINK_THRESHOLD_CACHE
    threshold = 0.50
    try:
        row = db.conn.execute(
            "SELECT value FROM settings WHERE key = 'auto_link_threshold'"
        ).fetchone()
        if row:
            try:
                threshold = float(row["value"])
                threshold = max(0.0, min(1.0, threshold))
            except (ValueError, TypeError):
                pass
    except Exception:
        pass
    with _AUTO_LINK_THRESHOLD_LOCK:
        _AUTO_LINK_THRESHOLD_CACHE = threshold
        _AUTO_LINK_THRESHOLD_TS = now
    return threshold


class TripMatcher:
    """Top-level entry point for matching an import to a trip.

    Constructor takes the same :class:`DatabaseManager` instance used
    everywhere else in the app; repositories are instantiated from it.
    Stateless — ``match()`` is safe to call from worker threads.
    """

    # Tunable thresholds.  Can be overridden by the caller (e.g. from
    # settings) once the settings UI is in place.
    AUTO_ATTACH_THRESHOLD = 0.95
    SUGGEST_THRESHOLD = 0.70
    AUTO_LINK_THRESHOLD_DEFAULT = 0.50
    RECENT_FALLBACK_DAYS = 30
    RECENT_FALLBACK_LIMIT = 20

    def __init__(self, db, *, auto_attach_threshold: float = 0.95,
                 suggest_threshold: float = 0.70,
                 auto_link_threshold: float | None = None,
                 recent_fallback_days: int = RECENT_FALLBACK_DAYS,
                 recent_fallback_limit: int = RECENT_FALLBACK_LIMIT) -> None:
        self.db = db
        self.trips = TripRepository(db)
        self.clients = ClientRepository(db)
        self.contacts = ContactRepository(db)
        self.invoices = InvoiceRepository(db)
        self.auto_attach_threshold = auto_attach_threshold
        self.suggest_threshold = suggest_threshold
        self.auto_link_threshold = (
            auto_link_threshold
            if auto_link_threshold is not None
            else _load_auto_link_threshold(db)
        )
        self.recent_fallback_days = recent_fallback_days
        self.recent_fallback_limit = recent_fallback_limit
        self._weights = _load_weights(db)
        self._weights_cache_ts: float = time.time()

    def match(
        self,
        extracted: dict[str, str],
        ocr_text: str = "",
        source_filename: str = "",
    ) -> MatchResult:
        """Score candidate trips for this import.

        ``extracted`` is the dict produced by
        :class:`OcrExtractor.extract()` (the ``.extracted`` field of
        :class:`ExtractionResult`).
        """
        # Refresh weights cache periodically.
        if time.time() - self._weights_cache_ts > 60:
            self._weights = _load_weights(self.db)
            self._weights_cache_ts = time.time()
        w = self._weights

        signals: dict[str, float] = {}
        per_trip: dict[int, dict[str, float]] = {}

        def _bump(trip_id: int, key: str, score: float) -> None:
            if score <= 0:
                return
            entry = per_trip.setdefault(trip_id, {})
            entry[key] = max(entry.get(key, 0.0), float(score))

        # ── 1. CMR number ─────────────────────────────────────────────
        cmr = (extracted.get("cmr_number") or "").strip()
        if cmr:
            try:
                matches = self.trips.get_by_cmr_number(cmr)
            except Exception:
                matches = []
                logger.exception("CMR lookup failed")
            for t in matches:
                _bump(t["id"], "cmr", w.get("cmr", 0.35))
            signals["cmr"] = min(1.0, len(matches) / 1.0)

        # ── 2. Invoice number ─────────────────────────────────────────
        inv = (extracted.get("invoice_number") or "").strip()
        if inv:
            try:
                matches = self.trips.get_by_invoice_via_trip_invoice(inv)
            except Exception:
                matches = []
                logger.exception("Invoice lookup failed")
            for t in matches:
                _bump(t["id"], "invoice", w.get("invoice", 0.30))
            signals["invoice"] = min(1.0, len(matches) / 1.0)

        # ── 3. Client name (fuzzy) ────────────────────────────────────
        client_name = (extracted.get("consignee") or extracted.get("consignor") or "").strip()
        if client_name:
            try:
                candidates = self.trips.get_by_client_name_fuzzy(client_name, limit=25)
            except Exception:
                candidates = []
                logger.exception("Client lookup failed")
            for t in candidates:
                score = _fuzzy_score(client_name, t.get("client_name") or "")
                if score > 0.4:
                    _bump(t["id"], "client", w.get("client", 0.20) * score)
            if candidates:
                signals["client"] = w.get("client", 0.20) * _fuzzy_score(
                    client_name, candidates[0].get("client_name") or ""
                )

        # ── 3b. Company stamp (fuzzy match against DB clients) ──────
        stamp_fields = [
            extracted.get("consignor_stamp"),
            extracted.get("consignee_stamp"),
            extracted.get("haulier_stamp"),
            extracted.get("consignor"),
            extracted.get("consignee"),
        ]
        stamp_names = {s.strip() for s in stamp_fields if s and s.strip()}
        seen_stamp_trips: set[int] = set()
        for stamp_name in stamp_names:
            try:
                matching_clients = self.clients.search_by_name(stamp_name, fuzzy=True, limit=5)
            except Exception:
                matching_clients = []
                logger.exception("Client search for stamp '%s' failed", stamp_name)
            if not matching_clients:
                continue
            best_client_score = max(
                _fuzzy_score(stamp_name, (c.get("name") or "").strip())
                for c in matching_clients
            )
            if best_client_score <= 0.4:
                continue
            for client in matching_clients:
                try:
                    client_trips = self.trips.get_by_client_name_fuzzy(
                        client.get("name", ""), limit=10,
                    )
                except Exception:
                    client_trips = []
                    logger.exception("Trip lookup for stamp client failed")
                for t in client_trips:
                    if t["id"] not in seen_stamp_trips:
                        seen_stamp_trips.add(t["id"])
                        _bump(t["id"], "company_stamp", w.get("company_stamp", 0.25) * best_client_score)

        # ── 4. Plate ──────────────────────────────────────────────────
        plate = (extracted.get("truck_plate") or "").strip()
        trailer = (extracted.get("trailer_plate") or "").strip()
        for plate_value in (plate, trailer):
            norm = normalize_plate(plate_value)
            if not norm:
                continue
            try:
                matches = self.trips.get_by_truck_plate(norm)
            except Exception:
                matches = []
                logger.exception("Plate lookup failed")
            for t in matches:
                _bump(t["id"], "plate", w.get("plate", 0.10))
            if matches:
                signals["plate"] = signals.get("plate", 0.0) + w.get("plate", 0.10)

        # ── 5. Driver name (fuzzy) ────────────────────────────────────
        driver = (extracted.get("driver_name") or "").strip()
        if driver:
            try:
                matches = self.trips.get_by_driver_name(driver)
            except Exception:
                matches = []
                logger.exception("Driver lookup failed")
            for t in matches:
                score = _fuzzy_score(driver, t.get("driver_name") or "")
                if score > 0.5:
                    _bump(t["id"], "driver", w.get("driver", 0.05) * score)
            if matches:
                signals["driver"] = w.get("driver", 0.05) * _fuzzy_score(
                    driver, matches[0].get("driver_name") or ""
                )

        # ── 6. Date proximity (with temporal decay) ──────────────────
        date_str = (extracted.get("date") or "").strip()
        if not date_str:
            m = re.search(r"\b(20\d{2}[./\-]\d{1,2}[./\-]\d{1,2})\b", ocr_text)
            if m:
                date_str = m.group(1)
        if date_str:
            normalized = normalize_date(date_str)
            try:
                matches = self.trips.get_trips_by_date_proximity(normalized)
            except Exception:
                matches = []
                logger.exception("Date proximity lookup failed")
            base_w = w.get("date", 0.05)
            for t in matches:
                # Temporal decay: trips further from the target date score less.
                trip_date = t.get("start_date", "")[:10] if t.get("start_date") else ""
                decay = 1.0
                if trip_date and normalized:
                    try:
                        days_apart = abs(
                            (datetime.strptime(trip_date, "%Y-%m-%d") -
                             datetime.strptime(normalized[:10], "%Y-%m-%d")).days
                        )
                        decay = max(0.1, 1.0 - days_apart / 60.0)
                    except (ValueError, TypeError):
                        pass
                _bump(t["id"], "date", base_w * decay)
            if matches:
                signals["date"] = base_w

        # ── 8. Geographic proximity ──────────────────────────────────
        loading = (extracted.get("loading_place") or "").strip()
        delivery = (extracted.get("delivery_place") or "").strip()
        geo_w = w.get("geographic", 0.10)
        # Batch-fetch candidate trip rows ONCE — geographic scoring and
        # final scoring both need them, so we store in ``trip_rows`` and
        # skip the redundant fetch that the final-scoring section used
        # to do.
        trip_ids = list(per_trip.keys())
        trip_rows: dict[int, dict[str, Any]] = {}
        for chunk_start in range(0, len(trip_ids), 100):
            chunk = trip_ids[chunk_start:chunk_start + 100]
            placeholders = ",".join("?" for _ in chunk)
            try:
                rows = self.db.conn.execute(
                    f"SELECT * FROM trips WHERE id IN ({placeholders})",
                    tuple(chunk),
                ).fetchall()
                for r in rows:
                    trip_rows[int(r["id"])] = dict(r)
            except Exception:
                logger.exception("Batch trip fetch failed")
        if (loading or delivery) and trip_rows:
            for t in trip_rows.values():
                trip_origin = (t.get("origin") or t.get("origin_city") or "").strip()
                trip_dest = (t.get("destination") or t.get("destination_city") or "").strip()
                loading_score = _geo_fuzzy_score(loading, trip_origin) if loading else 0.0
                delivery_score = _geo_fuzzy_score(delivery, trip_dest) if delivery else 0.0
                combined = max(loading_score, delivery_score)
                if combined > 0.3:
                    _bump(t["id"], "geographic", geo_w * combined)

        # ── 7. Filename hints ─────────────────────────────────────────
        hints = _filename_hints(source_filename)
        filename_auto_attach = False
        if "trip_id_hint" in hints:
            try:
                trip_row = self.trips.get_by_id(int(hints["trip_id_hint"]))
            except (ValueError, TypeError):
                trip_row = None
            if trip_row:
                # Trip ID in filename is a strong signal — score high
                # enough to reach the auto-attach threshold.
                _bump(trip_row["id"], "filename", 0.95)
                signals["filename"] = 0.95
                filename_auto_attach = True
        if not filename_auto_attach and "date_hint" in hints:
            try:
                normalized = normalize_date(hints["date_hint"])
                matches = self.trips.get_trips_by_date_proximity(normalized)
            except Exception:
                matches = []
            for t in matches:
                _bump(t["id"], "date", w.get("date", 0.05) * 3)
            if matches:
                signals["date"] = signals.get("date", 0.0) + w.get("date", 0.05) * 3
        if not filename_auto_attach and "plate_hint" in hints:
            try:
                matches = self.trips.get_by_truck_plate(hints["plate_hint"])
            except Exception:
                matches = []
            for t in matches:
                _bump(t["id"], "filename", w.get("filename", 0.05) * 4)
            if matches:
                signals["filename"] = signals.get("filename", 0.0) + w.get("filename", 0.05) * 4

        # ── Fallback: if no candidates at all, return recent trips ──
        if not per_trip:
            try:
                recent = self.trips.get_recent_trips_for_matching(
                    days_back=self.recent_fallback_days,
                    limit=self.recent_fallback_limit,
                )
            except Exception:
                recent = []
                logger.exception("Recent-trips fallback failed")
            candidates = [
                MatchCandidate(
                    trip=t,
                    confidence=0.01,
                    signals={"fallback_recent": 1.0},
                )
                for t in recent[:5]
            ]
            return MatchResult(
                best_match=None,
                confidence=0.0,
                candidates=candidates,
                signals=signals,
            )

        # ── Final scoring ─────────────────────────────────────────────
        # trip_rows was already populated by the geographic-proximity
        # section if it ran.  If not (no loading/delivery fields were
        # extracted), fetch them now.  Either way, a single batch query
        # is used — previously the geographic section and this section
        # each fetched the same rows, doubling the DB load.
        if not trip_rows:
            trip_ids = list(per_trip.keys())
            for chunk_start in range(0, len(trip_ids), 100):
                chunk = trip_ids[chunk_start:chunk_start + 100]
                placeholders = ",".join("?" for _ in chunk)
                try:
                    rows = self.db.conn.execute(
                        f"SELECT * FROM trips WHERE id IN ({placeholders})",
                        tuple(chunk),
                    ).fetchall()
                    for r in rows:
                        trip_rows[int(r["id"])] = dict(r)
                except Exception:
                    logger.exception("Batch trip fetch failed")

        # Determine document type for weight adjustment.
        doc_type = (extracted.get("doc_type") or "other").strip().lower()
        type_mult = _DOC_TYPE_MULTIPLIERS.get(doc_type, {})

        ranked: list[MatchCandidate] = []
        for trip_id, sig_map in per_trip.items():
            trip_row = trip_rows.get(int(trip_id))
            if trip_row is None:
                continue
            # Apply document-type multipliers to each signal.
            adjusted = {
                k: v * type_mult.get(k, 1.0)
                for k, v in sig_map.items()
            }
            score = min(sum(adjusted.values()), 1.0)
            ranked.append(
                MatchCandidate(
                    trip=trip_row,
                    confidence=score,
                    signals=sig_map,
                )
            )
        ranked.sort(key=lambda c: c.confidence, reverse=True)
        ranked = ranked[:5]

        best = ranked[0] if ranked else None
        confidence = best.confidence if best else 0.0
        return MatchResult(
            best_match=best.trip if best else None,
            confidence=confidence,
            candidates=ranked,
            signals=signals,
        )
