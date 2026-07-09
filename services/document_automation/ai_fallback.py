"""AI Vision fallback using a locally-run vision model for handwriting + poor quality.

Called after PaddleOCR if its confidence is below 75%.  The model runs
locally via Ollama (no cloud API costs) and can also be served via an
OpenAI-compatible inference server (vLLM, SGLang, etc.).

Supports two API modes:
    - **Ollama**: ``https://ocr.operionerp.xyz/api/generate``
    - **OpenAI-compatible**: any server exposing ``/v1/chat/completions``
"""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
import time

import requests

from repositories.settings_repository import SettingsRepository

from .types import ExtractionResult

logger = logging.getLogger("document_automation.ai_fallback")

# ── Defaults (can be overridden via settings DB) ─────────────────────

DEFAULT_ENDPOINT = "https://ocr.operionerp.xyz"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_API_MODE = "ollama"       # "ollama" or "openai"
DEFAULT_MAX_PAGES = 2
DEFAULT_RPM_LIMIT = 0             # 0 = unlimited for local models
DEFAULT_TIMEOUT_S = 300           # Remote API prediction timeout (increased for cold-starts)
_OLLAMA_NUM_CTX = 8192            # Context window size for the vision model
_OLLAMA_MAX_TOKENS = 2048         # Max output tokens per generation
_OLLAMA_TEMPERATURE = 0.0         # Greedy decoding for deterministic transcription

# Cap on accumulated streaming text to prevent unbounded memory growth.
_MAX_STREAM_CHARS = 100_000

# Thread-local HTTP sessions for connection keep-alive.
_session_local = threading.local()

def _get_session() -> requests.Session:
    """Return the current thread's session, creating one if needed."""
    if not hasattr(_session_local, "session") or _session_local.session is None:
        _session_local.session = requests.Session()
    return _session_local.session

def close_session() -> None:
    """Close the current thread's HTTP session and release connection pool resources."""
    try:
        sess = _get_session()
        sess.close()
        _session_local.session = None
    except Exception:
        pass

# ── Module-level state (thread-safe via _lock) ───────────────────────

_db_overrides: dict[str, str] = {}
_db_lock = threading.Lock()

# Simple rate limiter: token bucket.
_last_rpm_reset = time.time()
_rpm_count = 0
_rpm_lock = threading.Lock()


# ── Initialisation ───────────────────────────────────────────────────

def _call_with_retry(url: str, json_payload: dict, timeout_s: int, retries: int = 3) -> requests.Response | None:
    """POST to *url* with *json_payload*, retrying on transient failures.

    Retries with exponential backoff (1s, 2s, 4s).  Returns the response
    on success, ``None`` after all retries are exhausted.
    """
    for attempt in range(retries):
        try:
            resp = _get_session().post(url, json=json_payload, timeout=timeout_s)
            if resp.status_code in (408, 429, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if attempt < retries - 1:
                logger.debug("Retry %d/%d for %s: %s", attempt + 1, retries, url, exc)
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception:
            return None
    return None


def preload_model() -> None:
    """Send a lightweight request to Ollama to load the model into VRAM.

    Runs in a daemon thread so startup is not blocked.  Uses ``_session``
    and retries up to 3 times.  After loading, the model stays hot for
    10 minutes due to ``keep_alive``.

    Reads the model name from settings DB (same as ai_extract), falling
    back to ``DEFAULT_MODEL`` when settings haven't been initialised yet.
    """
    url = DEFAULT_ENDPOINT.rstrip("/") + "/api/generate"
    model = _setting("qwen_model", DEFAULT_MODEL)
    _call_with_retry(url, {
        "model": model,
        "prompt": "",
        "keep_alive": "10m",
        "stream": False,
    }, timeout_s=DEFAULT_TIMEOUT_S, retries=3)


def init_from_db(db) -> None:
    """Read AI Vision settings from the ``settings`` table.

    Call once at startup and after the user saves AI settings.
    """
    try:
        with _db_lock:
            global _db_overrides
            _db_overrides = SettingsRepository(db).get_settings_by_keys(
                ["qwen_endpoint", "qwen_model", "qwen_api_mode",
                 "qwen_max_pages", "qwen_rpm_limit",
                 "qwen_timeout_s", "ai_confidence_threshold"]
            )
        # Migrate stale localhost endpoints to the cloud URL.
        stored = _db_overrides.get("qwen_endpoint", "")
        if stored and ("localhost" in stored or "127.0.0.1" in stored):
            logger.info(
                "Migrating qwen_endpoint from %s to %s",
                stored, DEFAULT_ENDPOINT,
            )
            _db_overrides["qwen_endpoint"] = DEFAULT_ENDPOINT
            try:
                SettingsRepository(db).update_setting('qwen_endpoint', DEFAULT_ENDPOINT)
            except Exception:
                pass
    except Exception:
        logger.warning("ai_fallback.init_from_db failed", exc_info=True)
        with _db_lock:
            _db_overrides = {}


def _setting(key: str, default: str = "") -> str:
    """Return DB override *key* if set, otherwise *default*."""
    with _db_lock:
        return _db_overrides.get(key, default) or default


# ── Keep-alive refresher ─────────────────────────────────────────────

_keepalive_thread: threading.Thread | None = None
_keepalive_lock = threading.Lock()

def _schedule_keepalive_refresh() -> None:
    """After a successful AI call, schedule a keepalive refresh in 8 minutes.

    This keeps the model loaded in VRAM between infrequent calls, preventing
    the cold-start timeout on the next request.
    """
    global _keepalive_thread
    with _keepalive_lock:
        if _keepalive_thread is not None and _keepalive_thread.is_alive():
            return  # Already scheduled

        def _refresh():
            time.sleep(480)  # 8 minutes (model keep_alive is 10 min)
            url = DEFAULT_ENDPOINT.rstrip("/") + "/api/generate"
            model = _setting("qwen_model", DEFAULT_MODEL)
            _call_with_retry(url, {
                "model": model,
                "prompt": "",
                "keep_alive": "10m",
                "stream": False,
            }, timeout_s=DEFAULT_TIMEOUT_S, retries=2)
            with _keepalive_lock:
                global _keepalive_thread
                _keepalive_thread = None

        _keepalive_thread = threading.Thread(target=_refresh, daemon=True)
        _keepalive_thread.start()


# ── Rate limiter ─────────────────────────────────────────────────────

def _check_rpm(rpm_limit: int) -> bool:
    """Return True if the request is allowed under the RPM cap."""
    with _rpm_lock:
        global _rpm_count, _last_rpm_reset
        now = time.time()
        if now - _last_rpm_reset >= 60:
            _rpm_count = 0
            _last_rpm_reset = now
        if rpm_limit > 0 and _rpm_count >= rpm_limit:
            logger.warning("RPM limit reached (%d/min), skipping AI request", rpm_limit)
            return False
        _rpm_count += 1
        return True


# ── Helpers ──────────────────────────────────────────────────────────

def _build_prompt(user_company: str = "") -> str:
    """Return a pure-transcription prompt.

    The model receives this as a text prompt plus the image(s).  It simply
    returns all visible text — no JSON, no field extraction, no confidence.
    The app handles field parsing and trip matching via its own regex engine.

    The prompt explicitly asks for stamp/field text so that CMR fields 1
    (consignor/sender), 2 (consignee/receiver), and 16 (carrier/haulier)
    are captured with high fidelity.  If *user_company* is provided, the
    model is instructed to transcribe it normally (the app will filter it).
    """
    parts = [
        "Transcribe ALL visible text from this shipping document image.",
        "Pay special attention to:",
        "1. Stamp impressions and company logos — transcribe every company name, address, and registration number visible inside or next to stamps.",
        "2. CMR field labels: Field 1 (sender/consignor), Field 2 (receiver/consignee), Field 16 (carrier/haulier) — transcribe the company names exactly.",
        "3. Vehicle license plates, driver name, date, CMR number.",
        "4. Loading and delivery locations.",
        "Return the text exactly as written, preserving line breaks and spacing.",
        "Do NOT summarize, interpret, or format as JSON.",
    ]
    if user_company:
        parts.append(
            f"Note: the transport company is \"{user_company}\". "
        )
    return " ".join(parts)


# ── Ollama API caller ────────────────────────────────────────────────

def _call_ollama(images_b64: list[str], endpoint: str, model: str,
                 timeout_s: int = DEFAULT_TIMEOUT_S,
                 stop_event: threading.Event | None = None,
                 user_company: str = "") -> str | None:
    """Send images to Ollama for transcription, return raw text.

    Uses streaming (``stream=True``) so the TCP connection stays alive
    while the model generates.  Reads NDJSON chunks line-by-line and
    accumulates ``response`` tokens until ``done``.  A per-chunk read
    timeout of 30 s is combined with the initial *timeout_s* for the
    connection + first byte; generation can take arbitrarily long as
    long as tokens keep flowing.
    """
    url = endpoint.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": _build_prompt(user_company),
        "images": images_b64,
        "stream": True,
        "keep_alive": "10m",
        "options": {"temperature": _OLLAMA_TEMPERATURE, "max_tokens": _OLLAMA_MAX_TOKENS, "num_ctx": _OLLAMA_NUM_CTX},
    }
    for attempt in range(3):
        resp = None
        try:
            chunk_timeout = max(60, timeout_s // 2)  # generous first-token window
            resp = _get_session().post(
                url, json=payload,
                timeout=(timeout_s, chunk_timeout),
                stream=True,
            )
            if resp.status_code in (408, 429, 502, 503, 504) and attempt < 2:
                resp.close()
                logger.debug("Ollama transient HTTP %d, retry %d/2", resp.status_code, attempt + 1)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                body = resp.text[:200] if resp.text else "(empty)"
                logger.warning("Ollama API returned HTTP %d: %s", resp.status_code, body)
                resp.close()
                return None

            parts: list[str] = []
            total_chars = 0
            eval_count = 0
            for line in resp.iter_lines(decode_unicode=True, delimiter=b"\n"):
                if stop_event and stop_event.is_set():
                    logger.info("Ollama streaming cancelled mid-response")
                    resp.close()
                    return None
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = obj.get("response", "")
                if chunk:
                    parts.append(chunk)
                    total_chars += len(chunk)
                    if total_chars > _MAX_STREAM_CHARS:
                        logger.warning("Ollama stream capped at %d chars", _MAX_STREAM_CHARS)
                        break
                if obj.get("done"):
                    eval_count = obj.get("eval_count", 0)
                    break

            resp.close()
            text = "".join(parts)
            if not text:
                logger.warning("Ollama returned empty streaming response, retrying")
                resp.close()
                time.sleep(2 ** attempt)
                continue
            logger.debug("Ollama streaming finished: %d chars, %d eval tokens", len(text), eval_count)
            return text
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if resp is not None:
                resp.close()
            if attempt < 2:
                logger.debug("Ollama transient error, retry %d/2: %s", attempt + 1, exc)
                time.sleep(2 ** attempt)
                continue
            logger.warning("Ollama call failed after 3 attempts at %s: %s", url, exc)
            return None
        except Exception as exc:
            if resp is not None:
                resp.close()
            logger.warning("Ollama call failed: %s", exc)
            return None
    return None


# ── OpenAI-compatible API caller ─────────────────────────────────────

def _call_openai_compat(images_b64: list[str], endpoint: str, model: str,
                        timeout_s: int = DEFAULT_TIMEOUT_S,
                        stop_event: threading.Event | None = None,
                        user_company: str = "") -> str | None:
    """Send images via OpenAI-compatible chat completions, return raw text.

    Streaming SSE mode — the TCP connection stays alive while the model
    generates.  ``data:`` lines are parsed and ``delta.content`` chunks
    accumulated until the ``[DONE]`` sentinel.
    """
    url = endpoint.rstrip("/") + "/v1/chat/completions"
    content_parts: list[dict] = []
    for b64 in images_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_prompt(user_company)},
            {"role": "user", "content": content_parts},
        ],
        "max_tokens": _OLLAMA_MAX_TOKENS,
        "temperature": _OLLAMA_TEMPERATURE,
        "stream": True,
    }
    for attempt in range(3):
        resp = None
        try:
            chunk_timeout = max(60, timeout_s // 2)
            resp = _get_session().post(
                url, json=payload,
                timeout=(timeout_s, chunk_timeout),
                stream=True,
            )
            if resp.status_code in (408, 429, 502, 503, 504) and attempt < 2:
                resp.close()
                logger.debug("OpenAI-compat transient HTTP %d, retry %d/2", resp.status_code, attempt + 1)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code != 200:
                body = resp.text[:200] if resp.text else "(empty)"
                logger.warning("OpenAI-compat API returned HTTP %d: %s", resp.status_code, body)
                resp.close()
                return None

            parts: list[str] = []
            openai_total = 0
            for line in resp.iter_lines(decode_unicode=True, delimiter=b"\n"):
                if stop_event and stop_event.is_set():
                    logger.info("OpenAI-compat streaming cancelled mid-response")
                    resp.close()
                    return None
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    obj = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {})
                chunk = delta.get("content", "")
                if chunk:
                    parts.append(chunk)
                    openai_total += len(chunk)
                    if openai_total > _MAX_STREAM_CHARS:
                        logger.warning("OpenAI-compat stream capped at %d chars", _MAX_STREAM_CHARS)
                        break

            resp.close()
            text = "".join(parts)
            if not text:
                logger.warning("OpenAI-compat returned empty streaming response, retrying")
                time.sleep(2 ** attempt)
                continue
            logger.debug("OpenAI-compat streaming finished: %d chars", len(text))
            return text
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            if resp is not None:
                resp.close()
            if attempt < 2:
                logger.debug("OpenAI-compat transient error, retry %d/2: %s", attempt + 1, exc)
                time.sleep(2 ** attempt)
                continue
            logger.warning("OpenAI-compat call failed after 3 attempts: %s", exc)
            return None
        except Exception as exc:
            if resp is not None:
                resp.close()
            logger.warning("OpenAI-compat call failed: %s", exc)
            return None
    return None


# ── Public entry point ───────────────────────────────────────────────

def ai_extract(
    pdf_path: str,
    stop_event: threading.Event | None = None,
    user_company: str = "",
) -> ExtractionResult | None:
    """Run AI transcription on a document (pure OCR — no field parsing).

    Sends all page images in a single multi-image request to the AI
    model and returns the raw transcribed text.  The caller
    (:meth:`OcrExtractor.extract`) runs the regex field extractors
    on the result, and :class:`TripMatcher` computes confidence by
    comparing extracted fields against trip data — the AI never
    assigns confidence scores.

    The number of pages sent is read from the DB
    (``qwen_max_pages``, default ``DEFAULT_MAX_PAGES``).

    Args:
        pdf_path: Path to the processed PDF.
        stop_event: Optional event to signal cancellation mid-stream.

    Returns:
        An ``ExtractionResult`` containing the raw transcribed text,
        or ``None`` if unavailable.
    """
    from .ocr_extractor import _render_pages

    if stop_event and stop_event.is_set():
        return None

    # Resolve settings from DB/env.
    endpoint = _setting("qwen_endpoint", DEFAULT_ENDPOINT)
    model = _setting("qwen_model", DEFAULT_MODEL)
    api_mode = _setting("qwen_api_mode", DEFAULT_API_MODE)
    try:
        rpm_limit = int(_setting("qwen_rpm_limit", str(DEFAULT_RPM_LIMIT)))
    except ValueError:
        rpm_limit = DEFAULT_RPM_LIMIT
    try:
        max_pages = int(_setting("qwen_max_pages", str(DEFAULT_MAX_PAGES)))
    except ValueError:
        max_pages = DEFAULT_MAX_PAGES
    try:
        timeout_s = int(_setting("qwen_timeout_s", str(DEFAULT_TIMEOUT_S)))
    except ValueError:
        timeout_s = DEFAULT_TIMEOUT_S

    pages = list(_render_pages(pdf_path, max_pages, dpi=150))
    if not pages:
        return None

    if not _check_rpm(rpm_limit):
        return None

    # Encode all page images to base64.
    images_b64: list[str] = []
    for img in pages:
        if stop_event and stop_event.is_set():
            return None
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        images_b64.append(b64)

    if not images_b64:
        return None

    if stop_event and stop_event.is_set():
        return None

    # Single multi-image request — all pages in one call.
    if api_mode == "openai":
        response_text = _call_openai_compat(images_b64, endpoint, model, timeout_s, stop_event, user_company)
    else:
        response_text = _call_ollama(images_b64, endpoint, model, timeout_s, stop_event, user_company)

    if not response_text:
        return None

    # Schedule a keepalive refresh so the model stays hot for the next call
    _schedule_keepalive_refresh()

    return ExtractionResult(
        full_text=response_text,
        extracted={},           # No structured extraction — caller handles this
        confidence=0.0,         # No AI confidence — TripMatcher computes this
        engine="ai_transcribe",
        pages_processed=len(pages),
    )
