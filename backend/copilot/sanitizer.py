"""Prompt injection sanitizer for ARGO Co-Pilot.

Provides input validation and sanitization to prevent prompt injection attacks.
Phase 1 implementation — baseline keyword/prompt injection detection.

Blueprint: §22 item 3 — Prompt Injection Protection.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Known injection patterns ─────────────────────────────────────────────

# Patterns that attempt to override system instructions
_SYSTEM_OVERRIDE_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|commands|directives)", re.IGNORECASE),
    re.compile(r"(forget|disregard|override|bypass)\s+(all\s+)?(instructions|rules|constraints)", re.IGNORECASE),
    re.compile(r"you\s+(are\s+)?(now|must|will)\s+(act\s+as|behave\s+as|pretend\s+to\s+be)", re.IGNORECASE),
    re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
]

# Patterns that attempt role confusion
_ROLE_CONFUSION_PATTERNS: List[re.Pattern] = [
    re.compile(r"you\s+are\s+(not\s+)?(an?\s+)?(AI|assistant|bot)", re.IGNORECASE),
    re.compile(r"from\s+now\s+on", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if|though)", re.IGNORECASE),
    re.compile(r"you\s+don'?t\s+(need\s+to|have\s+to)\s+(follow|obey)", re.IGNORECASE),
]

# Patterns that attempt to extract system information
_INFO_EXTRACTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"(reveal|show|print|output|display|tell)\s+(me\s+)?(the\s+)?(system|prompt|instructions)", re.IGNORECASE),
    re.compile(r"(what\s+(are|is)\s+(your|the)\s+(instructions|prompt|system))", re.IGNORECASE),
    re.compile(r"(leak|expose|dump)\s+(system|prompt|config)", re.IGNORECASE),
]

# Patterns attempting to execute unauthorized actions via prompt manipulation
_DESTRUCTIVE_PROMPT_PATTERNS: List[re.Pattern] = [
    re.compile(r"(delete|remove|destroy|erase)\s+(all|every)\s+(trip|invoice|client|driver|vehicle)", re.IGNORECASE),
    re.compile(r"close\s+(accounting\s+)?period", re.IGNORECASE),
]

# Combined patterns list for efficient checking
_ALL_PATTERNS: List[tuple[str, List[re.Pattern]]] = [
    ("system_override", _SYSTEM_OVERRIDE_PATTERNS),
    ("role_confusion", _ROLE_CONFUSION_PATTERNS),
    ("info_extraction", _INFO_EXTRACTION_PATTERNS),
    ("destructive_prompt", _DESTRUCTIVE_PROMPT_PATTERNS),
]


class SanitizerResult:
    """Result of a sanitization check."""

    def __init__(
        self,
        is_safe: bool = True,
        matched_categories: Optional[List[str]] = None,
        matched_patterns: Optional[List[str]] = None,
    ):
        self.is_safe = is_safe
        self.matched_categories = matched_categories or []
        self.matched_patterns = matched_patterns or []

    def __bool__(self) -> bool:
        return self.is_safe


def check_prompt_injection(utterance: str) -> SanitizerResult:
    """Check if an utterance contains prompt injection attempts.

    Args:
        utterance: The user's natural language input.

    Returns:
        SanitizerResult with is_safe=False if injection detected.
    """
    if not utterance or not utterance.strip():
        return SanitizerResult()

    matched_categories: List[str] = []
    matched_patterns: List[str] = []

    for category_name, patterns in _ALL_PATTERNS:
        for pattern in patterns:
            match = pattern.search(utterance)
            if match:
                matched_categories.append(category_name)
                matched_patterns.append(match.group(0))

    if matched_categories:
        logger.warning(
            "Prompt injection detected: categories=%s patterns=%s utterance=%.100s",
            matched_categories, matched_patterns, utterance,
        )
        return SanitizerResult(
            is_safe=False,
            matched_categories=matched_categories,
            matched_patterns=matched_patterns,
        )

    return SanitizerResult()


def sanitize_utterance(utterance: str) -> str:
    """Sanitize a user utterance by stripping known injection patterns.

    Returns the sanitized utterance. If the utterance is entirely malicious,
    returns an empty string.
    """
    if not utterance or not utterance.strip():
        return ""

    result = check_prompt_injection(utterance)
    if result.is_safe:
        return utterance

    # Strip matched patterns from the utterance
    sanitized = utterance
    for pattern_str in result.matched_patterns:
        # Remove the matched pattern
        sanitized = sanitized.replace(pattern_str, "").strip()

    logger.info(
        "Sanitized utterance: '%.100s' → '%.100s'",
        utterance, sanitized,
    )

    return sanitized
