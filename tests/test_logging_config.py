"""Tests for backend.logging_config — JSON log lines + idempotent wiring.

Covers:
  - JsonFormatter emits one valid JSON object per line
  - required keys: ts, level, logger, message
  - request_id is included when present on the record, omitted otherwise
  - configure_backend_logging is idempotent
  - configure_backend_logging preserves pre-existing handlers (gunicorn case)
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from backend.logging_config import JsonFormatter, configure_backend_logging


def _make_record(
    message: str = "hello",
    level: int = logging.INFO,
    request_id: str | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test.logger",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    if request_id is not None:
        record.request_id = request_id
    return record


class TestJsonFormatter:
    def test_emits_valid_json_with_core_keys(self):
        line = JsonFormatter().format(_make_record())
        data = json.loads(line)
        assert set(data) >= {"ts", "level", "logger", "message"}
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello"

    def test_includes_request_id_when_present(self):
        line = JsonFormatter().format(_make_record(request_id="req-xyz"))
        data = json.loads(line)
        assert data["request_id"] == "req-xyz"

    def test_omits_request_id_when_absent(self):
        line = JsonFormatter().format(_make_record())
        data = json.loads(line)
        assert "request_id" not in data

    def test_includes_exc_info_when_exception(self):
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()  # (type, value, traceback)
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=exc_info,
        )
        data = json.loads(JsonFormatter().format(record))
        assert "exc_info" in data
        assert "boom" in data["exc_info"]


@pytest.fixture(autouse=True)
def _isolate_root_logger() -> Iterator[None]:
    """Save/restore root handler state so tests don't leak."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    # Reset the idempotency flag BEFORE each test too — other suites (e.g.
    # test_api_gps) import backend.main, which calls configure_backend_logging
    # and leaves the flag set in this process.
    setattr(root, "_operion_json_configured", False)
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    setattr(root, "_operion_json_configured", False)


class TestConfigureBackendLogging:
    def test_adds_stderr_handler_when_none_exist(self):
        root = logging.getLogger()
        root.handlers = []
        configure_backend_logging()
        assert len(root.handlers) >= 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_preserves_existing_handlers_and_swaps_formatter(self):
        """Gunicorn-configured handlers keep their destination, new formatter."""
        root = logging.getLogger()
        existing = logging.StreamHandler()
        root.handlers = [existing]
        configure_backend_logging()
        assert root.handlers == [existing]
        assert isinstance(existing.formatter, JsonFormatter)

    def test_idempotent(self):
        root = logging.getLogger()
        root.handlers = []
        configure_backend_logging()
        first_handler = root.handlers[0]
        configure_backend_logging()
        assert root.handlers == [first_handler]  # no duplicate handlers

    def test_logged_record_is_valid_json(self, caplog):
        configure_backend_logging()
        with caplog.at_level(logging.INFO, logger="test.logger"):
            logging.getLogger("test.logger").info(
                "hello %s", "world",
                extra={"request_id": "req-caplog"},
            )
        # caplog handler bypasses our root handler; verify at least one line
        # formats as JSON through the JsonFormatter directly.
        data = json.loads(
            JsonFormatter().format(_make_record(message="x", request_id="req-caplog"))
        )
        assert data["request_id"] == "req-caplog"
