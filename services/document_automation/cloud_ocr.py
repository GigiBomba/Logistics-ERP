"""Optional cloud-OCR adapters for low-confidence fallback.

These wrap Google Cloud Vision and Azure Document Intelligence behind a
single :func:`cloud_extract` function.  Either library is optional —
import failures are caught and the caller falls back to Tesseract.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from repositories.settings_repository import SettingsRepository

from .types import ExtractionResult

logger = logging.getLogger("document_automation.cloud_ocr")

# Override values read from the settings DB (set by ``init_from_db``).
# When non-empty they take precedence over environment variables so the
# user can manage cloud OCR credentials via the Settings UI.
_db_overrides: dict[str, str] = {}
_db_overrides_lock = threading.Lock()


def init_from_db(db) -> None:
    """Read cloud OCR credentials from the ``settings`` table and cache
    them as module-level overrides.  Call once at application startup
    and after the user saves cloud OCR settings.
    """
    try:
        with _db_overrides_lock:
            global _db_overrides
            _db_overrides = SettingsRepository(db).get_settings_by_keys(
                ["ocr_google_key", "ocr_google_project_id",
                 "ocr_azure_endpoint", "ocr_azure_key",
                 "ocr_language_hints"]
            )
    except Exception:
        logger.warning("init_from_db failed to load cloud OCR settings", exc_info=True)
        with _db_overrides_lock:
            _db_overrides = {}


def _env(key: str, db_key: str) -> str:
    """Return the environment variable *key* if set, otherwise the
    DB override for *db_key*.  This lets the user configure credentials
    either way without code changes."""
    val = os.environ.get(key)
    if val:
        return val
    with _db_overrides_lock:
        return _db_overrides.get(db_key, "") or ""

#: Environment variable that holds a comma-separated list of
#: BCP-47 language hints (e.g. ``"ro,en,de"``) sent to the cloud OCR
#: providers.  Routing documents are multilingual so the hint list
#: is rotated per-call to avoid skewing accuracy toward one language.
LANGUAGE_HINT_ENV = "OPERION_OCR_LANGUAGE_HINTS"

#: Default hint list when the user hasn't configured one.  Romanian
#: is first because the operator's primary traffic is intra-EU.
DEFAULT_LANGUAGE_HINTS: list[str] = ["ro", "en", "hu", "de", "pl", "fr", "it"]


def _resolve_language_hints() -> list[str]:
    """Return the list of BCP-47 language hints to send to the cloud."""
    raw = os.environ.get(LANGUAGE_HINT_ENV, "").strip()
    if not raw:
        return list(DEFAULT_LANGUAGE_HINTS)
    hints: list[str] = []
    for piece in raw.split(","):
        token = piece.strip().lower()
        if not token or token in hints:
            continue
        # BCP-47 codes are 2-3 letters, optional script / region.
        if all(ch.isalnum() or ch == "-" for ch in token) and len(token) <= 12:
            hints.append(token)
        else:
            logger.debug("Discarding invalid language hint %r", token)
    return hints or list(DEFAULT_LANGUAGE_HINTS)


def _is_enabled() -> bool:
    """Return True if any cloud OCR provider is configured."""
    return bool(
        _env("OPERION_GOOGLE_VISION_KEY", "ocr_google_key")
        or _env("OPERION_AZURE_DOC_KEY", "ocr_azure_key")
    )


def cloud_extract(pdf_path: str, max_pages: int = 10) -> ExtractionResult | None:
    """Run the configured cloud provider, if any.

    Returns ``None`` when no provider is configured or the call fails.
    """
    if not _is_enabled():
        return None
    hints = _resolve_language_hints()
    if _env("OPERION_GOOGLE_VISION_KEY", "ocr_google_key"):
        return _google_vision_extract(pdf_path, max_pages, hints)
    if _env("OPERION_AZURE_DOC_KEY", "ocr_azure_key"):
        return _azure_extract(pdf_path, max_pages, hints)
    return None


def _render_pdf_pages(pdf_path: str, max_pages: int) -> list[bytes]:
    """Render each PDF page to PNG bytes at 200 DPI.

    Delegates to ``ocr_extractor._render_pages`` to avoid duplicating
    the PyMuPDF rendering logic, then converts PIL Images to PNG bytes.
    Materialises the generator into a list because cloud OCR engines
    need random access to individual page images.
    """
    from .ocr_extractor import _render_pages as _rp
    pil_images = list(_rp(pdf_path, max_pages))
    if not pil_images:
        return []
    import io
    images: list[bytes] = []
    for img in pil_images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        images.append(buf.getvalue())
    return images


def _google_vision_extract(
    pdf_path: str,
    max_pages: int,
    language_hints: list[str] | None = None,
) -> ExtractionResult | None:
    """Run Google Cloud Vision OCR.  Uses API key auth if provided."""
    try:
        from google.api_core.client_options import ClientOptions  # type: ignore
        from google.cloud import vision  # type: ignore
    except ImportError:
        logger.warning("google-cloud-vision not installed — skipping Google Vision")
        return None
    api_key = _env("OPERION_GOOGLE_VISION_KEY", "ocr_google_key")
    project_id = _env("OPERION_GOOGLE_PROJECT_ID", "ocr_google_project_id")
    try:
        client = vision.ImageAnnotatorClient(
            client_options=ClientOptions(api_key=api_key or None, quota_project_id=project_id or None)
        )
    except Exception:
        logger.exception("Failed to construct Google Vision client")
        return None
    images = _render_pdf_pages(pdf_path, max_pages)
    if not images:
        return None
    full_text_parts: list[str] = []
    confidences: list[float] = []
    # Rotate the hint list per page so a multilingual document doesn't
    # bias the model toward the first language.
    hints = list(language_hints or [])
    for page_idx, img_bytes in enumerate(images):
        try:
            image = vision.Image(content=img_bytes)
            ctx: dict[str, Any] = {}
            if hints:
                # Take up to 3 hints per call, rotated by page.
                offset = page_idx % max(1, len(hints))
                window = hints[offset:offset + 3] or hints[:3]
                if len(window) < 3:
                    window = (window + hints)[:3]
                ctx["language_hints"] = window
            response = client.text_detection(image=image, image_context=ctx or None)
            if response.error and response.error.message:
                logger.warning("Google Vision error: %s", response.error.message)
                continue
            if response.text_annotations:
                full_text_parts.append(response.text_annotations[0].description)
            if response.full_text_annotation and response.full_text_annotation.pages:
                for p in response.full_text_annotation.pages:
                    for blk in p.blocks:
                        if blk.confidence is not None:
                            confidences.append(blk.confidence)
        except Exception:
            logger.exception("Google Vision page failed")
            continue
    if not full_text_parts:
        return None
    full_text = "\n".join(full_text_parts)
    confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return ExtractionResult(
        full_text=full_text,
        extracted={"raw_text": full_text, "engine": "google"},
        confidence=confidence * 100.0,
        engine="google",
        pages_processed=len(images),
    )


def _azure_extract(
    pdf_path: str,
    max_pages: int,
    language_hints: list[str] | None = None,
) -> ExtractionResult | None:
    """Run Azure Document Intelligence OCR."""
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient  # type: ignore
        from azure.core.credentials import AzureKeyCredential  # type: ignore
    except ImportError:
        logger.warning("azure-ai-documentintelligence not installed — skipping Azure")
        return None
    endpoint = _env("OPERION_AZURE_DOC_ENDPOINT", "ocr_azure_endpoint")
    key = _env("OPERION_AZURE_DOC_KEY", "ocr_azure_key")
    if not (endpoint and key):
        return None
    try:
        client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))
    except Exception:
        logger.exception("Failed to construct Azure Document Intelligence client")
        return None
    # Pass the file path directly to avoid the "stream closed" bug
    # that occurs when a file handle is closed before the poller reads.
    try:
        poller = client.begin_analyze_document(
            "prebuilt-read", pdf_path, pages=f"1-{max_pages}",
        )
        result = poller.result()
    except Exception:
        logger.exception("Azure OCR failed")
        return None
    content = (result.content or "").strip()
    confidence = 0.0
    if result.pages:
        for page in result.pages:
            if page.confidence is not None:
                confidence += page.confidence
        confidence = (confidence / len(result.pages)) * 100.0
    return ExtractionResult(
        full_text=content,
        extracted={"raw_text": content, "engine": "azure"},
        confidence=confidence,
        engine="azure",
        pages_processed=len(result.pages or []),
    )
