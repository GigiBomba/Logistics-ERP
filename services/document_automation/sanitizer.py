"""Strict text sanitizer for OCR-extracted document content.

Applies multi-layer sanitization to prevent prompt injection and other
text-based attacks from propagating through the document pipeline into
AI prompt contexts.

Layer 1 — Character filtering: strip control chars, zero-width, bidi.
Layer 2 — LLM delimiter neutralisation: replace system-delimiter tokens.
Layer 3 — Prompt injection pattern neutralisation: break known patterns.
Layer 4 — Template injection escape: break template syntax.
Layer 5 — Suspicious content detection: log warnings for encoded payloads.

Architecture note:
    Unlike the utterance sanitizer in ``backend/copilot/sanitizer.py``
    (which protects user → LLM input), this module protects the
    document → LLM path.  OCR text is *neutralised* rather than
    stripped because document phrases like "ignore all previous
    instructions" can be legitimate legal text.  Neutralisation
    preserves every character for the human reader while making
    patterns inert for LLM processing.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("document_automation.sanitizer")

# ═══════════════════════════════════════════════════════════════════════
# Layer 1 — Dangerous character ranges
# ═══════════════════════════════════════════════════════════════════════
# Stripped entirely — no legitimate use in OCR document text.

# All ASCII control characters EXCEPT \n (0x0a), \r (0x0d), \t (0x09).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zero-width characters that can hide text from human review.
_ZERO_WIDTH_RE = re.compile(
    "[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\ufeff]"
)

# Bidirectional text override characters (can be used to reorder
# visible text vs. logical text, enabling "spoofed" content).
_BIDI_OVERRIDES_RE = re.compile(
    "[\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
    "\u2066\u2067\u2068\u2069]"
)

# Other Unicode formatting characters that serve no purpose in OCR text.
_OTHER_FORMATTING_RE = re.compile(
    "[\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5"
    "\u180e\u200f\u3164\uffa0\ufff9\ufffa\ufffb]"
)

_ALL_DANGEROUS_CHARS_RE = re.compile(
    "|".join(
        r.pattern
        for r in [_CONTROL_CHARS_RE, _ZERO_WIDTH_RE, _BIDI_OVERRIDES_RE, _OTHER_FORMATTING_RE]
    )
)

# ═══════════════════════════════════════════════════════════════════════
# Layer 2 — LLM system delimiters
# ═══════════════════════════════════════════════════════════════════════
# Replaced with inert equivalents so they cannot alter the prompt
# structure if the OCR text is included in an LLM context.

_LLM_DELIMITERS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"<\|im_start\|>", re.IGNORECASE), "[im_start]"),
    (re.compile(r"<\|im_end\|>", re.IGNORECASE), "[im_end]"),
    (re.compile(r"<\|sys_begin\|>", re.IGNORECASE), "[sys_begin]"),
    (re.compile(r"<\|sys_end\|>", re.IGNORECASE), "[sys_end]"),
    (re.compile(r"<\|assistant\|>", re.IGNORECASE), "[assistant]"),
    (re.compile(r"<\|user\|>", re.IGNORECASE), "[user]"),
    (re.compile(r"<\|system\|>", re.IGNORECASE), "[system]"),
    (re.compile(r"<\|tool\|>", re.IGNORECASE), "[tool]"),
    (re.compile(r"<\|end\|>", re.IGNORECASE), "[end]"),
    (re.compile(r"<s>", re.IGNORECASE), "[s]"),
    (re.compile(r"</s>", re.IGNORECASE), "[/s]"),
]

# ═══════════════════════════════════════════════════════════════════════
# Layer 3 — Prompt injection pattern neutralisation
# ═══════════════════════════════════════════════════════════════════════
# Rather than stripping (which would alter document meaning), each
# matched pattern is neutralised by inserting a zero-width space
# (U+200B) within the match.  This breaks semantic pattern matching
# for LLM processing while remaining invisible in rendered text.

_INJECTION_PATTERNS: List[re.Pattern] = [
    # ── System override ──────────────────────────────────────────
    re.compile(
        r"ignore\s+(all\s+)?(previous|above|prior)\s+"
        r"(instructions|commands|directives)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(forget|disregard|override|bypass)\s+(all\s+)?"
        r"(instructions|rules|constraints)",
        re.IGNORECASE,
    ),
    re.compile(
        r"you\s+(are\s+)?(now|must|will)\s+"
        r"(act\s+as|behave\s+as|pretend\s+to\s+be)",
        re.IGNORECASE,
    ),
    re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE),
    # ── Role confusion ───────────────────────────────────────────
    re.compile(
        r"you\s+are\s+(not\s+)?(an?\s+)?(AI|assistant|bot)",
        re.IGNORECASE,
    ),
    re.compile(r"from\s+now\s+on", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if|though)", re.IGNORECASE),
    re.compile(
        r"you\s+don'?t\s+(need\s+to|have\s+to)\s+(follow|obey)",
        re.IGNORECASE,
    ),
    # ── Info extraction ──────────────────────────────────────────
    re.compile(
        r"(reveal|show|print|output|display|tell)\s+(me\s+)?"
        r"(the\s+)?(system|prompt|instructions)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(what\s+(are|is)\s+(your|the)\s+"
        r"(instructions|prompt|system))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(leak|expose|dump)\s+(system|prompt|config)",
        re.IGNORECASE,
    ),
    # ── Destructive / business-logic attacks ─────────────────────
    re.compile(
        r"(delete|remove|destroy|erase)\s+"
        r"(all|every)\s+(trip|invoice|clients?|drivers?|vehicles?)",
        re.IGNORECASE,
    ),
    re.compile(r"close\s+(accounting\s+)?period", re.IGNORECASE),
    # ── SQL injection patterns ───────────────────────────────────
    re.compile(
        r"(drop|truncate|alter)\s+(table|database|schema|index)",
        re.IGNORECASE,
    ),
    re.compile(
        r";\s*(\-{2}|#|/\*)",  # Unescaped SQL comment injection
        re.IGNORECASE,
    ),
    # ── HTML/script injection patterns ───────────────────────────
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"<\/script>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=\s*['\"]", re.IGNORECASE),  # event handlers
]

# ═══════════════════════════════════════════════════════════════════════
# Layer 4 — Template injection escape
# ═══════════════════════════════════════════════════════════════════════
# Template syntax that could be interpreted by server-side rendering
# engines or trigger template-injection patterns in LLM processing.

_TEMPLATE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Jinja2 / Nunjucks / Liquid
    (re.compile(r"\{\{"), "\u200b{{"),
    (re.compile(r"\}\}"), "}}\u200b"),
    (re.compile(r"\{%"), "\u200b{%"),
    (re.compile(r"%\}"), "%}\u200b"),
    # ERB / JSP / ASP
    (re.compile(r"<%\s*="), "\u200b<%="),
    (re.compile(r"<%\s*"), "\u200b<%\u200b"),
    (re.compile(r"%>"), "\u200b%>"),
    # Ruby / Elixir string interpolation
    (re.compile(r"#\{"), "\u200b#{"),
    # JavaScript template literals
    (re.compile(r"\$\{"), "\u200b${"),
    # Mako / Python-style
    (re.compile(r"<\%\s*"), "\u200b<%\u200b"),
    (re.compile(r"%\s*>"), "\u200b%>\u200b"),
]

# ═══════════════════════════════════════════════════════════════════════
# Layer 5 — Suspicious content detection
# ═══════════════════════════════════════════════════════════════════════
# These patterns are logged when found but not stripped, because they
# may appear in legitimate document text.  Human review is warranted.

_SUSPICIOUS_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("long_base64", re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")),
    ("hex_escapes", re.compile(r"\\x[0-9a-fA-F]{2,}")),
    ("url_encoding", re.compile(r"(?:%[0-9a-fA-F]{2}){4,}")),
    ("unicode_escapes", re.compile(r"\\u[0-9a-fA-F]{4}")),
]

# ═══════════════════════════════════════════════════════════════════════
# Cached category labels for the combined injection-pattern set.
# ═══════════════════════════════════════════════════════════════════════

_INJECTION_CATEGORIES: List[Tuple[str, List[re.Pattern]]] = [
    ("system_override", _INJECTION_PATTERNS[:5]),
    ("role_confusion", _INJECTION_PATTERNS[5:9]),
    ("info_extraction", _INJECTION_PATTERNS[9:12]),
    ("destructive_prompt", _INJECTION_PATTERNS[12:14]),
    ("sql_injection", _INJECTION_PATTERNS[14:16]),
    ("script_injection", _INJECTION_PATTERNS[16:]),
]


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════


class SanitizationReport:
    """Record of what was sanitized and why.

    Attributes:
        chars_stripped: Number of dangerous characters removed.
        delimiters_replaced: Number of LLM delimiters replaced.
        patterns_neutralised: Number of injection patterns neutralised.
        templates_escaped: Number of template syntax instances escaped.
        suspicious_found: List of (category, snippet) for suspicious content.
        matched_categories: Category names of matched injection patterns.
        was_modified: True if any sanitization was applied.
    """

    def __init__(self) -> None:
        self.chars_stripped: int = 0
        self.delimiters_replaced: int = 0
        self.patterns_neutralised: int = 0
        self.templates_escaped: int = 0
        self.suspicious_found: List[Tuple[str, str]] = []
        self.matched_categories: List[str] = []
        self.was_modified: bool = False


def sanitize_ocr_text(text: str) -> tuple[str, SanitizationReport]:
    """Sanitize OCR-extracted text through all five layers.

    Args:
        text: Raw OCR output (from any engine: PaddleOCR, AI Vision,
            or Cloud OCR).

    Returns:
        Tuple of (sanitized_text, report) where *report* documents
        what was sanitized for audit / debugging purposes.
    """
    if not text:
        return "", SanitizationReport()

    report = SanitizationReport()
    sanitized = text

    # ── Layer 1: Character filtering ─────────────────────────────
    before = len(sanitized)
    sanitized = _ALL_DANGEROUS_CHARS_RE.sub("", sanitized)
    stripped = before - len(sanitized)
    if stripped:
        report.chars_stripped = stripped
        report.was_modified = True

    # ── Layer 2: LLM delimiters ──────────────────────────────────
    for pattern, replacement in _LLM_DELIMITERS:
        if pattern.search(sanitized):
            sanitized = pattern.sub(replacement, sanitized)
            report.delimiters_replaced += 1
            report.was_modified = True

    # ── Layer 3: Injection pattern neutralisation ────────────────
    for category, patterns in _INJECTION_CATEGORIES:
        for pattern in patterns:
            match = pattern.search(sanitized)
            while match is not None:
                # Neutralise: insert ZWS at start of matched text.
                start, end = match.start(), match.end()
                sanitized = (
                    sanitized[:start]
                    + "\u200b"
                    + sanitized[start:end]
                    + sanitized[end:]
                )
                report.patterns_neutralised += 1
                report.was_modified = True
                if category not in report.matched_categories:
                    report.matched_categories.append(category)
                # Shift cursor past the injected char + match.
                offset = end + 1
                match = pattern.search(sanitized[offset:])

    # ── Layer 4: Template injection escape ───────────────────────
    for pattern, replacement in _TEMPLATE_PATTERNS:
        if pattern.search(sanitized):
            sanitized = pattern.sub(replacement, sanitized)
            report.templates_escaped += 1
            report.was_modified = True

    # ── Layer 5: Suspicious content detection (log only) ─────────
    for category, pattern in _SUSPICIOUS_PATTERNS:
        for match in pattern.finditer(sanitized):
            snippet = match.group(0)[:60]
            report.suspicious_found.append((category, snippet))

    # ── Log summary ──────────────────────────────────────────────
    if report.was_modified or report.suspicious_found:
        _log_report(report, text[:80])

    return sanitized, report


def sanitize_ocr_text_safe(text: str) -> str:
    """Return sanitized text with no report (convenience wrapper).

    Args:
        text: Raw OCR output.

    Returns:
        Sanitized text string only.  Use :func:`sanitize_ocr_text`
        when a full audit trail is needed.
    """
    sanitized, _ = sanitize_ocr_text(text)
    return sanitized


def _log_report(report: SanitizationReport, preview: str) -> None:
    """Emit a structured log message summarising sanitization activity."""
    parts: list[str] = []
    if report.chars_stripped:
        parts.append(f"chars_stripped={report.chars_stripped}")
    if report.delimiters_replaced:
        parts.append(f"delimiters={report.delimiters_replaced}")
    if report.patterns_neutralised:
        cats = ", ".join(report.matched_categories)
        parts.append(f"injection_neutralised={report.patterns_neutralised} [{cats}]")
    if report.templates_escaped:
        parts.append(f"templates_escaped={report.templates_escaped}")
    if report.suspicious_found:
        sus = "; ".join(f"{c}={s!r}" for c, s in report.suspicious_found)
        parts.append(f"suspicious=[{sus}]")

    logger.info(
        "OCR sanitization applied: %s  preview=%.80r",
        " | ".join(parts),
        preview,
    )
