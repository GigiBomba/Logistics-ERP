"""Top-level OCR orchestrator.

Strategy (tried in order, each falling back to the next):
    1. PaddleOCR   — primary engine (handwriting + printed).
    2. AI Vision   — GPT-4V / Claude for handwriting, poor quality (triggered when PaddleOCR conf < 75%).
    3. Cloud OCR   — Google Vision / Azure, final fallback (triggered when AI conf < 75%).
    4. Apply the regex extractors in :mod:`field_extractors` to the
       raw text and return the final :class:`ExtractionResult`.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import threading
import time

import numpy as np  # type: ignore

from .field_extractors import extract_fields, normalize_date
from .types import ExtractionResult, OcrLine

logger = logging.getLogger("document_automation.ocr")


def _endpoint_reachable(url: str, timeout: float = 10.0) -> bool:
    """Return ``True`` if *url* responds to a HEAD request within *timeout* seconds.

    Used to skip the AI Vision thread when the inference server is down,
    avoiding the 120-second read timeout on every pipeline run.
    """
    try:
        import requests as _req
        try:
            r = _req.head(url, timeout=timeout, allow_redirects=True)
            return r.ok
        except _req.ConnectionError:
            return False
        except _req.Timeout:
            return False
    except ImportError:
        return False

# ── PaddleOCR (primary engine) ───────────────────────────────────────

# Map translation codes to PaddleOCR language models.
# The ``latin`` model covers nearly all Latin-script EU languages
# including Romanian, English, German, French, Spanish, Italian, etc.
_PADDLE_LANG_MAP: dict[str, str] = {
    "bg": "latin", "bs": "latin", "cs": "latin", "de": "latin",
    "el": "greek", "en": "latin", "es": "latin", "fr": "latin",
    "hr": "latin", "hu": "latin", "it": "latin", "nl": "latin",
    "pl": "latin", "pt": "latin", "ro": "latin", "ru": "cyrillic",
    "sk": "latin", "sl": "latin", "sr": "cyrillic", "sv": "latin",
    "tr": "latin", "uk": "cyrillic",
}

_PADDLE_OCR_INSTANCE = None
_PADDLE_OCR_LOCK = threading.Lock()
_PADDLE_USE_GPU = False
# PaddleOCR detection resolution cap — prevents OOM on high-res scans.
# 960 px on the longest side preserves enough detail for CMR text while
# keeping memory below ~4 GB (vs ~43 GB uncapped at 300 DPI).
_PADDLE_DET_LIMIT_SIDE_LEN = 960
_PADDLE_DET_LIMIT_TYPE = "max"
_PADDLE_REC_BATCH_NUM = 6

# Field name aliases from AI/cloud engines → internal field names.
_FIELD_ALIASES = {
    "vehicle_registration": "truck_plate",
    "trailer_registration": "trailer_plate",
    "loading_location": "loading_place",
    "delivery_location": "delivery_place",
}

# ── Configurable PaddleOCR confidence threshold ──────────────────────
# Cached from the ``settings`` table so callers that don't hold a DB
# reference (e.g. ``OcrExtractor()`` created without ``db``) still get
# a reasonable default.
_PADDLE_CONF_THRESHOLD_CACHE: float = 40.0
_PADDLE_CONF_THRESHOLD_TS: float = 0
_PADDLE_CONF_THRESHOLD_TTL = 60  # seconds
_PADDLE_CONF_THRESHOLD_LOCK = threading.Lock()

# Confidence value assigned when the field-count boost activates.
# Must be above ``_local_confidence_threshold`` so the PaddleOCR
# result is accepted without falling through to AI Vision.
_PADDLE_FIELD_BOOST_CONFIDENCE = 99.0


def _load_paddle_confidence_threshold(db=None) -> float:
    """Return the PaddleOCR confidence threshold from the settings DB.

    Falls back to ``40.0`` when *db* is ``None``, the table is missing,
    or the key ``paddle_confidence_threshold`` is not set.  Results are
    cached for ``_PADDLE_CONF_THRESHOLD_TTL`` seconds to avoid hammering
    the DB on every document import.
    """
    global _PADDLE_CONF_THRESHOLD_CACHE, _PADDLE_CONF_THRESHOLD_TS
    now = time.time()
    with _PADDLE_CONF_THRESHOLD_LOCK:
        if (now - _PADDLE_CONF_THRESHOLD_TS) < _PADDLE_CONF_THRESHOLD_TTL:
            return _PADDLE_CONF_THRESHOLD_CACHE
    threshold = 40.0
    if db is not None:
        try:
            row = db.conn.execute(
                "SELECT value FROM settings WHERE key = 'paddle_confidence_threshold'"
            ).fetchone()
            if row:
                try:
                    threshold = float(row["value"])
                    threshold = max(0.0, min(100.0, threshold))
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass
    with _PADDLE_CONF_THRESHOLD_LOCK:
        _PADDLE_CONF_THRESHOLD_CACHE = threshold
        _PADDLE_CONF_THRESHOLD_TS = now
    return threshold


def set_paddle_gpu(enable: bool) -> None:
    """Enable/disable GPU for PaddleOCR.

    PaddleOCR v3.x uses PaddlePaddle's device setting, not a
    constructor parameter.  Called from the worker thread after
    reading the user's preference from the settings DB.
    """
    global _PADDLE_USE_GPU
    _PADDLE_USE_GPU = bool(enable)
    if _PADDLE_USE_GPU:
        try:
            import paddle
            paddle.device.set_device('gpu:0')
        except Exception:
            pass


def set_paddle_config(*,
                      det_limit_side_len: int | None = None,
                      det_limit_type: str | None = None,
                      rec_batch_num: int | None = None) -> None:
    """Tune PaddleOCR parameters before the singleton is created.
    Has no effect after the first call to ``_paddle_extract``
    (the singleton is already constructed).

    Parameter names match PaddleOCR v3.x constructor:
        - ``text_det_limit_side_len`` (was ``det_limit_side_len``)
        - ``text_det_limit_type`` (was ``det_limit_type``)
        - ``text_recognition_batch_size`` (was ``rec_batch_num``)
    """
    global _PADDLE_DET_LIMIT_SIDE_LEN, _PADDLE_DET_LIMIT_TYPE, _PADDLE_REC_BATCH_NUM
    if det_limit_side_len is not None:
        _PADDLE_DET_LIMIT_SIDE_LEN = det_limit_side_len
    if det_limit_type is not None:
        _PADDLE_DET_LIMIT_TYPE = det_limit_type
    if rec_batch_num is not None:
        _PADDLE_REC_BATCH_NUM = rec_batch_num


def _resolve_paddle_lang() -> str:
    """Return the PaddleOCR language code that covers the widest
    range of our supported translation languages.
    ``ro`` (Romanian) uses the ``latin`` model which covers all
    Latin-script EU languages in a single model."""
    return "ro"


def _safe_import_paddleocr():
    try:
        import paddleocr  # type: ignore
        return paddleocr
    except ImportError:
        return None


def _parse_paddle_output(raw_result) -> list[OcrLine]:
    """Convert PaddleOCR ``predict()`` output to structured ``OcrLine`` list.

    PaddleOCR v3.x returns::

        list[list[tuple[list[float], tuple[str, float]]]]

    where the outer list is per-page *groups* (multi-column documents
    produce more than one group per rendered page), each group contains
    tuples of ``(bbox, (text, confidence))``.

    Encapsulating the fragile index-based access in a single function
    protects the rest of the codebase from PaddleOCR API changes —
    only this function needs updating if the return format changes.
    """
    lines: list[OcrLine] = []
    if not raw_result:
        return lines
    for page_group in raw_result:
        if page_group is None:
            continue
        for entry in page_group:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            text_info = entry[1]
            if not isinstance(text_info, (list, tuple)) or len(text_info) < 2:
                continue
            raw_text = text_info[0] or ""
            text = str(raw_text).strip()
            if not text:
                continue
            try:
                confidence = float(text_info[1])
            except (TypeError, ValueError):
                confidence = 0.0
            bbox = list(entry[0]) if isinstance(entry[0], (list, tuple)) else None
            lines.append(OcrLine(text=text, confidence=confidence, bbox=bbox))
    return lines


def _paddle_extract(pdf_path: str, max_pages: int) -> ExtractionResult | None:
    """Run PaddleOCR over the rendered pages.

    Falls back to ``None`` when PaddleOCR is not installed or
    encounters a non-recoverable error — the caller should fall
    through to cloud OCR.
    """
    global _PADDLE_OCR_INSTANCE
    paddleocr_mod = _safe_import_paddleocr()
    if paddleocr_mod is None:
        return None

    # Monkey-patch PaddlePaddle inference to disable MKLDNN, fixing the
    # oneDNN attribute conversion bug in PaddlePaddle 3.3.x:
    # ``ConvertPirAttribute2RuntimeAttribute not support``.
    try:
        import paddle.inference as _pdi
        if not hasattr(_pdi, '_opencode_patched'):
            _orig_fn = _pdi.create_predictor
            def _patched_fn(config):
                config.disable_mkldnn()
                config.disable_onednn()
                return _orig_fn(config)
            _pdi.create_predictor = _patched_fn
            _pdi._opencode_patched = True
    except Exception:
        pass

    # Lazy-create the singleton PaddleOCR instance (thread-safe).
    if _PADDLE_OCR_INSTANCE is None:
        with _PADDLE_OCR_LOCK:
            if _PADDLE_OCR_INSTANCE is None:
                # GPU is set via paddle.device.set_device() in set_paddle_gpu().
                if _PADDLE_USE_GPU:
                    try:
                        import paddle
                        paddle.device.set_device('gpu:0')
                    except Exception:
                        pass
                _PADDLE_OCR_INSTANCE = paddleocr_mod.PaddleOCR(
                    lang=_resolve_paddle_lang(),
                    text_det_limit_type=_PADDLE_DET_LIMIT_TYPE,
                    text_det_limit_side_len=_PADDLE_DET_LIMIT_SIDE_LEN,
                    text_recognition_batch_size=_PADDLE_REC_BATCH_NUM,
                )

    text_parts: list[str] = []
    confidences: list[float] = []
    pages_processed = 0
    try:
        for img in _render_pages(pdf_path, max_pages):
            pages_processed += 1
            try:
                # PaddleOCR v3.x requires numpy.ndarray or str, not PIL Image.
                raw = _PADDLE_OCR_INSTANCE.predict(np.array(img.convert("RGB")))
                for ocr_line in _parse_paddle_output(raw):
                    text_parts.append(ocr_line.text)
                    confidences.append(ocr_line.confidence)
            except Exception as exc:
                logger.warning("PaddleOCR page failed: %s", exc)
    except Exception:
        return None

    if pages_processed == 0:
        logger.warning(
            "PaddleOCR: PDF yielded 0 pages — file may be corrupt. "
            "path=%s exists=%s size=%s",
            pdf_path, os.path.isfile(pdf_path),
            os.path.getsize(pdf_path) if os.path.isfile(pdf_path) else "N/A",
        )
        return ExtractionResult(
            full_text="", extracted={}, confidence=0.0,
            engine="paddle", pages_processed=0,
        )

    full_text = "\n".join(text_parts)
    confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
    return ExtractionResult(
        full_text=full_text,
        extracted={},
        confidence=confidence,
        engine="paddle",
        pages_processed=pages_processed,
    )


def _safe_import_fitz():
    try:
        import fitz  # type: ignore
        return fitz
    except ImportError:
        return None


def _render_pages(pdf_path: str, max_pages: int, dpi: int = 200):
    """Yield PIL images one at a time (lazy generator).

    Each page is rendered at *dpi* DPI (default 200).  PaddleOCR's
    internal text detection downsamples to 960 px anyway, so the
    extra resolution is discarded by the detector — 150 DPI is
    sufficient and saves ~50 % of the pixel count.  The AI Vision
    path passes ``dpi=150`` to reduce visual-token consumption
    inside the vision model.

    The generator keeps peak memory at O(1 x page_size) instead
    of O(N_pages x page_size) since the previous list accumulated
    every page before PaddleOCR could process the first one.

    The :class:`fitz.Document` is closed in a ``finally`` block so
    the underlying file handle is always released, even on error.
    """
    fitz = _safe_import_fitz()
    if fitz is None:
        return
    from PIL import Image  # type: ignore
    doc = None
    try:
        doc = fitz.open(pdf_path)
        page_count = min(max_pages, len(doc))
        for idx in range(page_count):
            page = doc.load_page(idx)
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img.load()
            yield img
    finally:
        if doc is not None:
            with contextlib.suppress(Exception):
                doc.close()


class OcrExtractor:
    """Stateless OCR entry point — safe to call from worker threads."""

    # Confidence threshold below which cloud OCR is tried.
    # PaddleOCR → AI Vision → Cloud OCR fallback chain thresholds.
    # If PaddleOCR confidence is below this, try AI Vision.
    # Lowered from 75.0 → 40.0 because PaddleOCR character-level
    # confidence is a poor proxy for overall OCR quality — decent
    # handwriting often scores 40-70% even when every character is
    # recognised correctly.  The field-count boost below catches
    # documents that have recognisable field patterns regardless
    # of average character confidence.
    LOCAL_CONFIDENCE_THRESHOLD = 40.0
    # If AI Vision confidence is below this, fall back to Cloud OCR.
    AI_CONFIDENCE_THRESHOLD = 75.0
    DEFAULT_MAX_PAGES = 10

    def __init__(self, max_pages: int = DEFAULT_MAX_PAGES, db=None) -> None:
        self.max_pages = max_pages
        # Load the configurable confidence threshold from the settings
        # DB.  Falls back to 40.0 when *db* is ``None`` or the key
        # ``paddle_confidence_threshold`` is not set.
        self._local_confidence_threshold = _load_paddle_confidence_threshold(db)

    def extract(self, pdf_path: str, stop_event: threading.Event | None = None,
                user_company: str = "") -> ExtractionResult:
        """Run OCR on ``pdf_path`` using PaddleOCR and AI Vision in
        parallel, picking whichever finishes with higher confidence.

        Strategy:
            1. Start PaddleOCR + AI Vision concurrently.
            2. Wait for both to finish (or up to a timeout).
            3. Pick the result with higher effective confidence.
            4. Fall back to Cloud OCR if both are below threshold.

        If *stop_event* is provided, the joins are polled every second
        and return early when the event is set, allowing the caller to
        cancel mid-OCR (e.g. during tab-switch shutdown).

        *user_company* is the logged-in transport company name — stamp
        field values matching it are filtered out.
        """
        import threading as _threading
        import time as _time

        _results: dict[str, ExtractionResult | None] = {}
        _lock = _threading.Lock()
        _stop = stop_event or _threading.Event()

        def _run_paddle():
            try:
                r = _paddle_extract(pdf_path, self.max_pages)
                with _lock:
                    _results["paddle"] = r
            except Exception as exc:
                logger.warning("PaddleOCR thread failed: %s", exc)
                with _lock:
                    _results["paddle"] = None

        def _run_ai():
            try:
                from .ai_fallback import DEFAULT_ENDPOINT, _setting, ai_extract
                actual_endpoint = _setting("qwen_endpoint", DEFAULT_ENDPOINT)
                if not _endpoint_reachable(actual_endpoint, timeout=10):
                    logger.info(
                        "AI Vision endpoint unreachable (%s) — skipping AI thread",
                        actual_endpoint,
                    )
                    with _lock:
                        _results["ai"] = None
                    return
                r = ai_extract(pdf_path, stop_event=_stop, user_company=user_company)
                with _lock:
                    _results["ai"] = r
            except ImportError:
                with _lock:
                    _results["ai"] = None
            except Exception as exc:
                logger.warning("AI Vision thread failed: %s", exc)
                with _lock:
                    _results["ai"] = None

        t_paddle = _threading.Thread(target=_run_paddle, daemon=True)
        t_ai = _threading.Thread(target=_run_ai, daemon=True)
        t_paddle.start()
        t_ai.start()

        deadline = _time.monotonic() + 300
        while _time.monotonic() < deadline:
            if _stop.is_set():
                break
            t_paddle.join(timeout=1)
            t_ai.join(timeout=1)
            if not t_paddle.is_alive() and not t_ai.is_alive():
                break

        paddle_result = _results.get("paddle")
        ai_result = _results.get("ai")

        # ── Helper: compute effective confidence with field boost ────
        # Uses a local cache to avoid re-extracting fields from the same text.
        _field_cache: dict[ExtractionResult, dict[str, str]] = {}

        def _effective(result: ExtractionResult | None) -> tuple:
            """Return (effective_confidence, result) or (0, None)."""
            if result is None or not result.full_text:
                return (0.0, None)
            fields = extract_fields(result.full_text, user_company=user_company)
            _field_cache[result] = fields
            fcount = sum(1 for v in fields.values() if v)
            conf = result.confidence
            if fcount >= 2:
                conf = max(conf, _PADDLE_FIELD_BOOST_CONFIDENCE)
            return (conf, result)

        p_conf, p_result = _effective(paddle_result)
        a_conf, a_result = _effective(ai_result)

        # ── Pick the best result ────────────────────────────────────
        if a_conf > p_conf:
            result = a_result
            result.confidence = a_conf
            logger.info(
                "OCR pick: AI Vision wins (conf=%.0f%% vs Paddle=%.0f%%)",
                a_conf, p_conf,
            )
        elif p_conf > 0:
            result = p_result
            result.confidence = p_conf
            logger.info(
                "OCR pick: PaddleOCR wins (conf=%.0f%%)",
                p_conf,
            )
        else:
            # Both failed — create empty result
            result = ExtractionResult("", {}, 0.0, "none", 0)
            logger.info("Both PaddleOCR and AI Vision failed — empty result")

        # ── Cloud OCR final fallback ────────────────────────────────
        if result.confidence < self.AI_CONFIDENCE_THRESHOLD:
            try:
                from .cloud_ocr import cloud_extract
                cloud = cloud_extract(pdf_path, max_pages=self.max_pages)
            except ImportError:
                cloud = None
            except Exception as exc:
                logger.warning("Cloud OCR unavailable, falling back: %s", exc)
                cloud = None
            if cloud is not None and cloud.full_text:
                c_conf, _ = _effective(cloud)
                if c_conf > result.confidence:
                    logger.info(
                        "Cloud OCR improves result (conf=%.0f%%)", c_conf,
                    )
                    result = cloud

        # ── Field extraction + aliasing (same as before) ────────────
        if result.extracted:
            extracted = dict(result.extracted)
            for ai_key, val in result.extracted.items():
                if val:
                    mapped_key = _FIELD_ALIASES.get(ai_key, ai_key)
                    extracted.setdefault(mapped_key, val)
            cn = result.extracted.get("client_name", "").strip()
            if cn:
                extracted.setdefault("consignee", cn)
        else:
            extracted = _field_cache.get(result) or extract_fields(result.full_text, user_company=user_company)
        extracted.setdefault("raw_text", result.full_text)
        if "date" in extracted:
            extracted["date"] = normalize_date(extracted["date"])
        if "cmr_number" in extracted:
            extracted.setdefault("doc_type", "cmr")
        elif "invoice_number" in extracted:
            extracted.setdefault("doc_type", "invoice")
        elif "package_count" in extracted or "weight_kg" in extracted:
            extracted.setdefault("doc_type", "delivery_note")
        else:
            extracted.setdefault("doc_type", "other")
        result.extracted = extracted
        return result
