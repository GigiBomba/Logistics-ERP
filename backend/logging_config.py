"""JSON logging configuration for the backend API.

Produces one JSON object per log line (timestamp, level, logger, message,
and ``request_id`` when present on the record) so logs are machine-parseable
for the observability stack.

§23.6/§29 additions:
- Correlation extras (``conversation_id``, ``company_id``, ``user_id``,
  ``phase``) are pulled from the telemetry ContextVars and attached to every
  JSON record emitted while the context is set (the router sets them at the
  request entry point). The formatter reads the ContextVars directly, so no
  caller has to remember ``extra={...}``.
- ``request_id`` falls back to the correlation middleware's ContextVar when
  the caller did not pass ``extra={"request_id": ...}``.
- PII redaction (§29) is applied to the ``message`` field (and any string
  structured fields) — emails, phone numbers, IBANs, Romanian CNPs and card
  numbers are replaced with ``[REDACTED]``. Exception tracebacks are NOT
  redacted (their source lines are developer output, not log messages).

``configure_backend_logging`` is idempotent and preserves existing behavior
when logging has already been configured (e.g. by gunicorn): it only swaps
the formatter on the already-installed root handlers, or installs a default
stderr handler when none exist.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone

_JSON_CONFIGURED_ATTR = "_operion_json_configured"


# ── Correlation context accessors ──────────────────────────────────────────
# Pulled lazily so this module stays importable in builds that ship without
# the ``backend`` package (packaged desktop client). ``telemetry`` only
# imports stdlib, so there is no import cycle here:
#   backend.logging_config -> backend.copilot.telemetry  (leaf module)
def _correlation_extras() -> dict:
    """Return the current telemetry correlation extras (may be empty)."""
    try:
        from backend.copilot.telemetry import (
            current_conversation_id,
            current_company_id,
            current_user_id,
            current_phase,
        )
        return {
            "conversation_id": current_conversation_id.get(),
            "company_id": current_company_id.get(),
            "user_id": current_user_id.get(),
            "phase": current_phase.get(),
        }
    except ImportError:
        return {}


def _request_id_from_context() -> str:
    """Return the correlation middleware's request id, or ``""``."""
    try:
        from backend.middleware.correlation_middleware import get_correlation_id
        return get_correlation_id()
    except ImportError:
        return ""


# ── PII redaction (§29) ────────────────────────────────────────────────────
# Simple regex-based redaction.  Applied to log *messages* only — exception
# tracebacks are intentionally excluded.  Patterns are ordered so broader
# structural patterns (email, IBAN) run before digit-run patterns that could
# otherwise consume part of them.

_REDACTED = "[REDACTED]"

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")
_E164_PHONE_PATTERN = re.compile(r"\+\d[\d\s.\-]{6,17}\b")
# Contiguous local numbers (9-15 digits): avoids 4-8 digit IDs / years / dates.
_LOCAL_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{9,15}(?!\d)")
# Grouped numbers such as "0722 123 456" / "(021) 305 12 34".  Dates like
# "2026-08-27" share this shape, so the replacement function only redacts
# matches with >= 10 digits (dates have 8).
_GROUPED_PHONE_PATTERN = re.compile(r"(?:\(?\d{2,4}\)?[\s.\-]?)?(?:\d{2,3}[\s.\-]?){2,3}\d{2,4}")
# Romanian CNP — 13 digits, first digit 1-9.
_CNP_PATTERN = re.compile(r"\b[1-9]\d{12}\b")
# Card numbers — 16-digit (optionally grouped) and Amex 15-digit.
_CARD16_PATTERN = re.compile(r"\b(?:\d{4}[ \-]?){3}\d{4}\b")
_AMEX_PATTERN = re.compile(r"\b\d{4}[ \-]?\d{6}[ \-]?\d{5}\b")


def _redact_grouped_phone(match: re.Match) -> str:
    """Redact grouped phone matches only when they contain >= 10 digits.

    Keeps date-like strings ("2026-08-27") intact while still redacting
    real grouped phone numbers ("0722 123 456").
    """
    digits = sum(ch.isdigit() for ch in match.group(0))
    return _REDACTED if digits >= 10 else match.group(0)


_PII_REDACTORS = (
    (_EMAIL_PATTERN, lambda m: _REDACTED),
    (_IBAN_PATTERN, lambda m: _REDACTED),
    (_E164_PHONE_PATTERN, lambda m: _REDACTED),
    (_CARD16_PATTERN, lambda m: _REDACTED),      # before grouped-phone: spaced card
    (_AMEX_PATTERN, lambda m: _REDACTED),        # numbers would otherwise be
    (_CNP_PATTERN, lambda m: _REDACTED),         # partially consumed as phones
    (_LOCAL_NUMBER_PATTERN, lambda m: _REDACTED),
    (_GROUPED_PHONE_PATTERN, _redact_grouped_phone),
)


def redact_pii(text: str) -> str:
    """Replace PII (email / phone / IBAN / CNP / card) with ``[REDACTED]``.

    Applied to log messages only; exception tracebacks are intentionally
    excluded from this pass.
    """
    if not text:
        return text
    for pattern, replacer in _PII_REDACTORS:
        text = pattern.sub(replacer, text)
    return text


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line: ts, level, logger, message, [...].

    Correlation extras (``conversation_id``, ``company_id``, ``user_id``,
    ``phase``) are attached from the current telemetry context when set
    (§23.6). ``request_id`` is picked up from ``record.request_id`` or the
    correlation middleware's context. The message (and string structured
    fields) pass through PII redaction (§29); exception tracebacks do not.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_pii(record.getMessage()),
        }
        for key, value in _correlation_extras().items():
            if value not in (None, "", 0):
                entry[key] = value
        request_id = getattr(record, "request_id", None) or _request_id_from_context()
        if request_id:
            entry["request_id"] = request_id
        for structured_field in ("method", "path", "status", "duration_ms"):
            value = getattr(record, structured_field, None)
            if value is not None:
                entry[structured_field] = (
                    redact_pii(value) if isinstance(value, str) else value
                )
        if record.exc_info and isinstance(record.exc_info, tuple):
            entry["exc_info"] = self.formatException(record.exc_info)
        try:
            return json.dumps(entry, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return json.dumps(
                {k: str(v) for k, v in entry.items()},
                ensure_ascii=False,
            )


def configure_backend_logging() -> None:
    """Configure the root logger with a JSON formatter (idempotent).

    - If handlers already exist (gunicorn configured logging), only their
      formatter is replaced — existing output destinations are preserved.
    - Otherwise a stderr ``StreamHandler`` is added and the root level is set
      to ``INFO``.
    - If the flag is set but every handler was subsequently removed (e.g. a
      framework reset), a fresh stderr handler is installed again.
    """
    root = logging.getLogger()
    if getattr(root, _JSON_CONFIGURED_ATTR, False) and root.handlers:
        return

    formatter = JsonFormatter()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(formatter)
        root.addHandler(handler)
        if root.level == logging.NOTSET or root.level > logging.INFO:
            root.setLevel(logging.INFO)

    setattr(root, _JSON_CONFIGURED_ATTR, True)