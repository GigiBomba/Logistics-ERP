"""Mode guard utility to prevent accidental local DB access in remote mode."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ConnectionMode(Enum):
    LOCAL = "local"    # Direct SQLite DB access
    REMOTE = "remote"  # API-only access
    UNKNOWN = "unknown"


def detect_mode(db, api_client) -> ConnectionMode:
    """Detect the connection mode. Logs warning if both or neither are provided."""
    has_db = db is not None
    has_api = api_client is not None

    if has_db and not has_api:
        return ConnectionMode.LOCAL
    elif has_api and not has_db:
        return ConnectionMode.REMOTE
    elif has_db and has_api:
        logger.warning(
            "Both db and api_client provided — this risks data leakage. "
            "Defaulting to LOCAL."
        )
        return ConnectionMode.LOCAL
    else:
        logger.warning(
            "Neither db nor api_client provided — running in degraded mode. "
            "Some features requiring local database access will be unavailable."
        )
        return ConnectionMode.UNKNOWN


def guard_local_access(mode: ConnectionMode, feature_name: str = "this feature"):
    """Raise if trying to use local DB in remote mode."""
    if mode == ConnectionMode.REMOTE:
        raise RuntimeError(
            f"{feature_name} requires local database access but app is in remote mode. "
            "This feature is not available when connected via API."
        )
