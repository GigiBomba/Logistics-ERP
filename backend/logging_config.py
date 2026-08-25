"""JSON logging configuration for the backend API.

Produces one JSON object per log line (timestamp, level, logger, message,
and ``request_id`` when present on the record) so logs are machine-parseable
for the observability stack.

``configure_backend_logging`` is idempotent and preserves existing behavior
when logging has already been configured (e.g. by gunicorn): it only swaps
the formatter on the already-installed root handlers, or installs a default
stderr handler when none exist.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_JSON_CONFIGURED_ATTR = "_operion_json_configured"


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per line: ts, level, logger, message, [request_id].

    ``request_id`` is picked up from ``record.request_id`` when the caller
    logs with ``extra={"request_id": ...}`` (e.g. the correlation middleware);
    records without it simply omit the key.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            entry["request_id"] = request_id
        for structured_field in ("method", "path", "status", "duration_ms"):
            value = getattr(record, structured_field, None)
            if value is not None:
                entry[structured_field] = value
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
