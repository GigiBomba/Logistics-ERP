"""i18n Scope — canonical list of shipped languages.

Blueprint: §3.1 — Language Scope.

This is a re-export for convenience. The canonical definition lives in
backend.copilot.schemas.SUPPORTED_LANGUAGES to avoid circular imports.
Every module that needs the language list imports from here.
"""
from __future__ import annotations


from backend.copilot.schemas import SUPPORTED_LANGUAGES  # noqa: F401 — re-export

__all__ = ["SUPPORTED_LANGUAGES"]
