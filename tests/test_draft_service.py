"""Tests for draft_service — uses tmp_path for file I/O."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Iterator
from unittest.mock import patch

import pytest

from services.draft_service import DraftService


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def draft_service(tmp_path: pytest.TempPathFactory) -> Iterator[DraftService]:
    """Return a DraftService rooted inside tmp_path so real FS is never touched."""
    drafts_root = os.path.join(str(tmp_path), "document_drafts")
    with patch("services.draft_service.DRAFTS_ROOT", drafts_root):
        service = DraftService(doc_type="invoice")
        service._dir = os.path.join(drafts_root, "invoice")
        os.makedirs(service._dir, exist_ok=True)
        yield service


# ── save ────────────────────────────────────────────────────────────


class TestSave:
    """DraftService.save() behaviour."""

    def test_save_creates_file(self, draft_service: DraftService, tmp_path: pytest.TempPathFactory) -> None:
        path = draft_service.save(42, {"key": "value"})
        assert os.path.exists(path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["key"] == "value"

    def test_save_adds_draft_saved_at_timestamp(
        self, draft_service: DraftService, tmp_path: pytest.TempPathFactory
    ) -> None:
        path = draft_service.save(1, {"a": 1})
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "_draft_saved_at" in data
        # Verify it looks like an ISO timestamp
        datetime.fromisoformat(data["_draft_saved_at"])

    def test_save_returns_file_path(self, draft_service: DraftService) -> None:
        path = draft_service.save(99, {"x": "y"})
        assert path.endswith("99.json")
        assert os.path.isabs(path)


# ── load ────────────────────────────────────────────────────────────


class TestLoad:
    """DraftService.load() behaviour."""

    def test_load_returns_dict(self, draft_service: DraftService) -> None:
        draft_service.save(7, {"hello": "world"})
        data = draft_service.load(7)
        assert isinstance(data, dict)
        assert data["hello"] == "world"

    def test_load_returns_none_for_missing(self, draft_service: DraftService) -> None:
        assert draft_service.load(999) is None

    def test_load_returns_none_for_corrupt_json(self, draft_service: DraftService) -> None:
        # Write a corrupt file manually
        bad_path = os.path.join(draft_service._dir, "corrupt.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("{this is not valid json")
        assert draft_service.load("corrupt") is None

    def test_load_returns_none_for_os_error(self, draft_service: DraftService) -> None:
        """An inaccessible file returns None (logged as warning)."""
        draft_service.save(5, {"a": 1})
        with patch("services.draft_service.open", side_effect=OSError("Permission denied")):
            result = draft_service.load(5)
        assert result is None


# ── delete ──────────────────────────────────────────────────────────


class TestDelete:
    """DraftService.delete() behaviour."""

    def test_delete_removes_file(self, draft_service: DraftService) -> None:
        draft_service.save(10, {"data": "test"})
        assert draft_service.delete(10) is True
        assert not os.path.exists(os.path.join(draft_service._dir, "10.json"))

    def test_delete_returns_false_for_missing(self, draft_service: DraftService) -> None:
        assert draft_service.delete(999) is False


# ── list_drafts ─────────────────────────────────────────────────────


class TestListDrafts:
    """DraftService.list_drafts() behaviour."""

    def test_list_drafts_returns_sorted_list(self, draft_service: DraftService) -> None:
        draft_service.save(1, {"name": "first"})
        draft_service.save(2, {"name": "second"})
        drafts = draft_service.list_drafts()
        assert len(drafts) == 2
        # Sorted by saved_at descending (most recent first)
        saved_times = [d["saved_at"] for d in drafts]
        assert saved_times == sorted(saved_times, reverse=True)

    def test_list_drafts_empty_dir(self, draft_service: DraftService) -> None:
        assert draft_service.list_drafts() == []

    def test_list_drafts_skips_non_json_files(self, draft_service: DraftService) -> None:
        draft_service.save(1, {"a": 1})
        # Drop a non-JSON file into the directory
        with open(os.path.join(draft_service._dir, "readme.txt"), "w") as f:
            f.write("not a draft")
        drafts = draft_service.list_drafts()
        assert len(drafts) == 1

    def test_list_drafts_skips_corrupt(self, draft_service: DraftService) -> None:
        draft_service.save(1, {"a": 1})
        bad_path = os.path.join(draft_service._dir, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            f.write("garbage")
        drafts = draft_service.list_drafts()
        # Only the valid draft is returned
        assert len(drafts) == 1


# ── cleanup_old_drafts ──────────────────────────────────────────────


class TestCleanupOldDrafts:
    """DraftService.cleanup_old_drafts() — classmethod, walks DRAFTS_ROOT."""

    def test_cleanup_old_drafts_removes_stale(self, tmp_path: pytest.TempPathFactory) -> None:
        drafts_root = os.path.join(str(tmp_path), "document_drafts")
        old_dir = os.path.join(drafts_root, "invoice")
        os.makedirs(old_dir, exist_ok=True)

        # Create a stale file (>30 days old)
        stale_path = os.path.join(old_dir, "stale.json")
        with open(stale_path, "w", encoding="utf-8") as f:
            json.dump({"a": 1}, f)
        stale_mtime = datetime.now() - timedelta(days=31)
        _set_mtime(stale_path, stale_mtime)

        # Create a recent file
        recent_path = os.path.join(old_dir, "recent.json")
        with open(recent_path, "w", encoding="utf-8") as f:
            json.dump({"b": 2}, f)

        with patch("services.draft_service.DRAFTS_ROOT", drafts_root):
            removed = DraftService.cleanup_old_drafts(max_age_days=30)

        assert removed == 1
        assert not os.path.exists(stale_path)
        assert os.path.exists(recent_path)

    def test_cleanup_old_drafts_no_stale(self, tmp_path: pytest.TempPathFactory) -> None:
        drafts_root = os.path.join(str(tmp_path), "document_drafts")
        recent_dir = os.path.join(drafts_root, "invoice")
        os.makedirs(recent_dir, exist_ok=True)

        recent_path = os.path.join(recent_dir, "fresh.json")
        with open(recent_path, "w", encoding="utf-8") as f:
            json.dump({"x": 1}, f)

        with patch("services.draft_service.DRAFTS_ROOT", drafts_root):
            removed = DraftService.cleanup_old_drafts(max_age_days=30)

        assert removed == 0
        assert os.path.exists(recent_path)

    def test_cleanup_old_drafts_skips_non_json(self, tmp_path: pytest.TempPathFactory) -> None:
        drafts_root = os.path.join(str(tmp_path), "document_drafts")
        old_dir = os.path.join(drafts_root, "invoice")
        os.makedirs(old_dir, exist_ok=True)

        txt_path = os.path.join(old_dir, "notes.txt")
        with open(txt_path, "w") as f:
            f.write("not a draft")
        old_mtime = datetime.now() - timedelta(days=60)
        _set_mtime(txt_path, old_mtime)

        with patch("services.draft_service.DRAFTS_ROOT", drafts_root):
            removed = DraftService.cleanup_old_drafts(max_age_days=30)

        assert removed == 0
        assert os.path.exists(txt_path)


def _set_mtime(path: str, dt: datetime) -> None:
    """Helper: set the mtime of *path* to *dt*."""
    timestamp = dt.timestamp()
    os.utime(path, (timestamp, timestamp))
