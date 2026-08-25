"""Backward-compatible shim for the refactored document_center sub-package.

Re-exports ``QtDocumentCenterView`` and ``open_entity_documents`` from
``ui/views/document_center/``.
"""
from __future__ import annotations


from ui.views.document_center.document_center import (  # noqa: F401
    QtDocumentCenterView,
    open_entity_documents,
)

__all__ = ["QtDocumentCenterView", "open_entity_documents"]
