from __future__ import annotations

import logging
import logging.handlers
import os
import sys

# Ensure logs directory exists once at module level
os.makedirs("logs", exist_ok=True)

# Track which loggers have been configured to prevent handler accumulation
_configured_loggers: set = set()

# ── Log rotation defaults (10 MB per file, keep 5 backups) ─────────────
ROTATING_MAX_BYTES = 10_000_000
ROTATING_BACKUP_COUNT = 5


def _make_file_handler(filename: str, formatter: logging.Formatter, delay: bool = False):
    """Create a rotating file handler pointed at *filename*.

    Replaces the unbounded ``FileHandler`` so ``logs/`` never grows without
    limit: the file rolls over at 10 MB and keeps 5 ``.1``/``.2``/… backups.
    """
    handler = logging.handlers.RotatingFileHandler(
        filename,
        maxBytes=ROTATING_MAX_BYTES,
        backupCount=ROTATING_BACKUP_COUNT,
        encoding="utf-8",
        delay=delay,
    )
    handler.setFormatter(formatter)
    return handler


def configure_app_logging(log_file: str, level: int = logging.INFO) -> None:
    """Central logging configuration for the desktop entry points.

    Single shared configuration so ``main.py`` and ``main_remote.py`` stay in
    sync: a rotating file handler (10 MB x 5 backups) plus stdout, with a
    timestamped file format.  Idempotent — ``force=True`` replaces any
    previously installed handlers on repeated calls.
    """
    log_dir = os.path.dirname(log_file) or "."
    os.makedirs(log_dir, exist_ok=True)

    file_handler = _make_file_handler(
        log_file,
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"),
        delay=True,
    )
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), file_handler],
        force=True,
    )


def get_logger(name, level=logging.INFO):
    """Create or reuse a logger. Route-specific debug logs go to 'logs/route_debug.log'.

    The function is intentionally simple: it writes route debug information to
    a dedicated file for easier diagnosis. Handlers are added only once per
    logger name to avoid accumulation.
    """
    logger = logging.getLogger(name)
    if name not in _configured_loggers:
        _configured_loggers.add(name)

        logger.propagate = False

        if name == "route_debug":
            handler = _make_file_handler(
                "logs/route_debug.log",
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            )
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        else:
            handler = _make_file_handler(
                "logs/app.log",
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            )
            logger.addHandler(handler)
            logger.setLevel(level)

    return logger
