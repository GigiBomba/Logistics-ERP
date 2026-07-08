"""Draft management service for document editors.

Saves and loads draft data for invoices, proformas, and receipts.
Extracted from invoice_editor.py, proforma_editor.py, and receipt_editor.py.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

DRAFTS_ROOT = os.path.join("data", "document_drafts")


class DraftService:
    """Save and load draft documents to/from JSON files.

    Draft files are stored in ``DRAFTS_ROOT/{doc_type}/`` with filenames
    like ``{doc_id}.json``.
    """

    def __init__(self, doc_type: str = "invoice"):
        self._doc_type = doc_type
        self._dir = os.path.join(DRAFTS_ROOT, doc_type)
        os.makedirs(self._dir, exist_ok=True)

    def save(self, doc_id: int | str, data: dict[str, Any]) -> str:
        """Save a draft to disk. Returns the file path."""
        path = os.path.join(self._dir, f"{doc_id}.json")
        data["_draft_saved_at"] = datetime.now().isoformat()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Draft saved: %s (%d bytes)", path, len(json.dumps(data)))
        return path

    def load(self, doc_id: int | str) -> dict[str, Any] | None:
        """Load a draft from disk. Returns None if not found."""
        path = os.path.join(self._dir, f"{doc_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load draft %s: %s", path, e)
            return None

    def delete(self, doc_id: int | str) -> bool:
        """Delete a draft file. Returns True if deleted."""
        path = os.path.join(self._dir, f"{doc_id}.json")
        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Draft deleted: %s", path)
                return True
            except OSError as e:
                logger.warning("Failed to delete draft %s: %s", path, e)
        return False

    def list_drafts(self) -> list[dict[str, Any]]:
        """List all saved drafts with metadata."""
        drafts = []
        if not os.path.exists(self._dir):
            return drafts
        for name in os.listdir(self._dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(self._dir, name)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                drafts.append({
                    "id": name.replace(".json", ""),
                    "path": path,
                    "saved_at": data.get("_draft_saved_at", ""),
                    "size": os.path.getsize(path),
                })
            except Exception:
                continue
        return sorted(drafts, key=lambda d: d["saved_at"], reverse=True)

    @classmethod
    def cleanup_old_drafts(cls, max_age_days: int = 30) -> int:
        """Delete drafts older than ``max_age_days``. Returns count removed."""
        from datetime import timedelta
        removed = 0
        cutoff = datetime.now() - timedelta(days=max_age_days)
        for root, _dirs, files in os.walk(DRAFTS_ROOT):
            for name in files:
                if not name.endswith(".json"):
                    continue
                path = os.path.join(root, name)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(path))
                    if mtime < cutoff:
                        os.remove(path)
                        removed += 1
                except OSError:
                    continue
        return removed
