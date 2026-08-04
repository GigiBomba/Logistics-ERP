"""Centralized input sanitization for all user-supplied data entering the app.

Covers the five input categories identified by the surface audit:
    1. Free-text fields (chat, search, notes, addresses, names)
    2. Structured JSON fields (API request bodies)
    3. File metadata (upload filenames, paths)
    4. Query/search parameters (URL query strings)
    5. Configuration values (settings, API keys, endpoints)

Each sanitizer function preserves legitimate content while removing or
neutralising known injection vectors.  The goal is defence-in-depth at
the application layer — Pydantic validation handles type safety, this
handles content-level threats.

Architecture:
    All public functions accept ``str`` and return ``str`` so they are
    composable and testable in isolation.  The :class:`RequestSanitizer`
    middleware class applies them to HTTP request bodies.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

# Maximum length for free-text user input fields.
_MAX_TEXT_LENGTH = 10_000
_MAX_SEARCH_LENGTH = 500
_MAX_FILENAME_LENGTH = 255

# Characters that are never legitimate in user text (strip entirely).
_STRIP_CHARS_RE = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"  # ASCII control (keep \n\r\t)
    "\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064"  # zero-width
    "\u200e\u200f\u202a\u202b\u202c\u202d\u202e"  # bidi overrides
    "\u2066\u2067\u2068\u2069\ufeff]"  # more bidi + BOM
)

# ── Prompt injection patterns (same as copilot/sanitizer.py) ──────────
_SYSTEM_OVERRIDE_RE = re.compile(
    r"(ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|commands|directives))"
    r"|((forget|disregard|override|bypass)\s+(all\s+)?(instructions|rules|constraints))"
    r"|(you\s+(are\s+)?(now|must|will)\s+(act\s+as|behave\s+as|pretend\s+to\s+be))"
    r"|(system\s*(prompt|message|instruction))"
    r"|(<\|im_start\|>|<\|im_end\|>)",
    re.IGNORECASE,
)

_ROLE_CONFUSION_RE = re.compile(
    r"(you\s+are\s+(not\s+)?(an?\s+)?(AI|assistant|bot))"
    r"|(from\s+now\s+on)"
    r"|(act\s+as\s+(if|though))"
    r"|(you\s+don'?t\s+(need\s+to|have\s+to)\s+(follow|obey))",
    re.IGNORECASE,
)

_INFO_EXTRACTION_RE = re.compile(
    r"((reveal|show|print|output|display|tell)\s+(me\s+)?"
    r"(the\s+)?(system|prompt|instructions))"
    r"|(what\s+(are|is)\s+(your|the)\s+(instructions|prompt|system))"
    r"|((leak|expose|dump)\s+(system|prompt|config))",
    re.IGNORECASE,
)

_DESTRUCTIVE_RE = re.compile(
    r"((delete|remove|destroy|erase)\s+(all|every)\s+"
    r"(trip|invoice|clients?|drivers?|vehicles?))"
    r"|(close\s+(accounting\s+)?period)",
    re.IGNORECASE,
)

_SQL_INJECTION_RE = re.compile(
    r"((drop|truncate|alter)\s+(table|database|schema|index))"
    r"|(;\s*(\-{2}|#|/\*))",
    re.IGNORECASE,
)

_SCRIPT_INJECTION_RE = re.compile(
    r"(<script[\s>])|(<\/script>)|(javascript\s*:)|(on\w+\s*=\s*['\"])",
    re.IGNORECASE,
)

# Combined prompt-injection pattern for efficient checking.
_PROMPT_INJECTION_RE = re.compile(
    "|".join(
        r.pattern
        for r in [
            _SYSTEM_OVERRIDE_RE,
            _ROLE_CONFUSION_RE,
            _INFO_EXTRACTION_RE,
            _DESTRUCTIVE_RE,
            _SQL_INJECTION_RE,
            _SCRIPT_INJECTION_RE,
        ]
    )
)

# ── Filename unsafe characters ───────────────────────────────────────
_FILENAME_UNSAFE_RE = re.compile(r'[\0\n\r\t\\/:*?"<>|]')

# ── Suspicious content patterns (log only, never strip) ──────────────
_SUSPICIOUS_BASE64_RE = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
_SUSPICIOUS_ESCAPE_RE = re.compile(r"(\\x[0-9a-fA-F]{2,})|(%[0-9a-fA-F]{2}){4,}")


# ═══════════════════════════════════════════════════════════════════════
# Public API — text-level sanitizers
# ═══════════════════════════════════════════════════════════════════════


def sanitize_free_text(text: str, *, max_length: int = _MAX_TEXT_LENGTH) -> str:
    """Sanitize free-text user input (chat, notes, addresses, descriptions).

    Applies:
        1. Dangerous character removal (control, zero-width, bidi).
        2. Length capping.
        3. Prompt-injection pattern breaking via ZWS insertion.
        4. Newline/whitespace normalisation.

    Preserves the original meaning for legitimate text.
    """
    if not text:
        return ""
    result = _strip_dangerous_chars(text)
    result = _cap_length(result, max_length)
    result = _neutralise_injection(result)
    result = _normalise_whitespace(result)
    return result


def sanitize_search_query(query: str) -> str:
    """Sanitize a search/filter query string.

    More aggressive trimming than free-text — search queries don't need
    long text, newlines, or special characters.
    """
    if not query:
        return ""
    result = _strip_dangerous_chars(query)
    result = _cap_length(result, _MAX_SEARCH_LENGTH)
    result = result.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    result = _neutralise_injection(result)
    return result.strip()[: _MAX_SEARCH_LENGTH]


def sanitize_filename(filename: str) -> str:
    """Sanitize a user-supplied filename for safe storage.

    Strips or replaces:
        - Path separators and unsafe chars (\\/:*?"<>|).
        - Control characters.
        - Leading/trailing dots and spaces.
        - Length cap at 255 bytes.
    """
    if not filename:
        return "untitled"
    # Remove path components — user may include absolute/relative paths.
    result = os.path.basename(filename)
    # Strip dangerous characters.
    result = _STRIP_CHARS_RE.sub("", result)
    result = _FILENAME_UNSAFE_RE.sub("_", result)
    # Collapse consecutive underscores/spaces.
    result = re.sub(r"[_\s]+", "_", result)
    # Strip leading/trailing dots, spaces, underscores.
    result = result.strip(". _")
    # Ensure non-empty and length-capped.
    if not result:
        result = "untitled"
    # Truncate to byte length (not char length) since filesystems use bytes.
    while len(result.encode("utf-8")) > _MAX_FILENAME_LENGTH:
        result = result[:-1]
    return result


def sanitize_json_field(value: Any, *, max_length: int = _MAX_TEXT_LENGTH) -> Any:
    """Recursively sanitize string values in a JSON-compatible structure.

    Applies :func:`sanitize_free_text` to every string it encounters.
    Non-string values are passed through unchanged.
    """
    if isinstance(value, str):
        return sanitize_free_text(value, max_length=max_length)
    if isinstance(value, dict):
        return {k: sanitize_json_field(v, max_length=max_length) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json_field(item, max_length=max_length) for item in value]
    return value


def sanitize_setting_value(key: str, value: str) -> str:
    """Sanitize a configuration setting value.

    Settings like API keys and endpoints need URL-safe sanitization
    (they are technical values, not natural text).
    """
    if not value:
        return ""
    # Only strip dangerous characters — don't neutralise injection
    # patterns because "system prompt" could be a legitimate key name.
    result = _STRIP_CHARS_RE.sub("", value)
    result = _cap_length(result, _MAX_TEXT_LENGTH)
    return result


def contains_injection(text: str) -> Tuple[bool, List[str]]:
    """Check if text contains known injection patterns.

    Returns:
        Tuple of ``(has_injection, matched_categories)``.
    """
    if not text:
        return False, []
    matched: List[str] = []
    if _SYSTEM_OVERRIDE_RE.search(text):
        matched.append("system_override")
    if _ROLE_CONFUSION_RE.search(text):
        matched.append("role_confusion")
    if _INFO_EXTRACTION_RE.search(text):
        matched.append("info_extraction")
    if _DESTRUCTIVE_RE.search(text):
        matched.append("destructive_prompt")
    if _SQL_INJECTION_RE.search(text):
        matched.append("sql_injection")
    if _SCRIPT_INJECTION_RE.search(text):
        matched.append("script_injection")
    return (len(matched) > 0, matched)


def detect_suspicious_content(text: str) -> List[Tuple[str, str]]:
    """Detect suspicious encoded payloads in text (log only, not stripped).

    Returns:
        List of ``(category, snippet)`` tuples.
    """
    findings: List[Tuple[str, str]] = []
    for match in _SUSPICIOUS_BASE64_RE.finditer(text):
        findings.append(("base64_payload", match.group(0)[:60]))
    for match in _SUSPICIOUS_ESCAPE_RE.finditer(text):
        findings.append(("escape_sequence", match.group(0)[:60]))
    if findings:
        logger.warning("Suspicious content detected: %s", findings)
    return findings


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════


def _strip_dangerous_chars(text: str) -> str:
    """Remove characters that serve no legitimate purpose in user input."""
    return _STRIP_CHARS_RE.sub("", text)


def _cap_length(text: str, max_length: int) -> str:
    """Cap text length at *max_length* characters."""
    if len(text) > max_length:
        logger.debug("Input truncated from %d to %d chars", len(text), max_length)
        return text[:max_length]
    return text


def _neutralise_injection(text: str, max_iterations: int = 20) -> str:
    """Insert zero-width space within known injection patterns.

    Uses ZWS (U+200B) to break pattern matching without altering visible
    content.  This preserves document meaning while making patterns
    inert for LLM processing.

    *max_iterations* prevents infinite loops from pathological inputs.
    """
    offset = 0
    for _ in range(max_iterations):
        match = _PROMPT_INJECTION_RE.search(text, offset)
        if match is None:
            break
        start, end = match.start(), match.end()
        text = text[:start] + "\u200b" + text[start:end] + text[end:]
        offset = end + 1
    return text


def _normalise_whitespace(text: str) -> str:
    """Normalise whitespace: collapse multiple spaces, trim."""
    text = re.sub(r"[ \t]+", " ", text)  # collapse spaces/tabs
    text = re.sub(r"\n{3,}", "\n\n", text)  # max 2 consecutive newlines
    return text.strip()
