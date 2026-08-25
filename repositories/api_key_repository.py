"""Repository for per-partner API key management.

Supports key generation (SHA-256 hashed storage), validation with
usage tracking, revocation, and listing — all scoped to the current
request's company context.
"""
from __future__ import annotations


import hashlib
import json
import secrets
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories import BaseRepository

logger = logging.getLogger(__name__)


class ApiKeyRepository(BaseRepository):
    """Manages API keys for external partner authentication.

    The plaintext key is returned **only once** at creation time.
    Only the SHA-256 hash is persisted.
    """

    TABLE = "api_keys"
    COLUMNS = [
        "key_hash", "key_prefix", "name", "partner", "scopes",
        "is_active", "created_by", "last_used_at", "expires_at",
        "revoked_at", "company_id",
    ]

    # ── Key lifecycle ──────────────────────────────────────────────────

    def create_key(
        self,
        name: str,
        partner: str,
        scopes: Optional[List[str]] = None,
        created_by: int = 0,
        expires_at: Optional[str] = None,
    ) -> tuple:
        """Generate a new API key and return ``(plaintext_key, key_id)``.

        The plaintext key is shown exactly once — store it immediately.
        The format is ``ok_<48 hex chars>`` (e.g. ``ok_a1b2c3…``).

        Args:
            name: Human-readable label (e.g. "TIMOCOM Production").
            partner: Partner slug (e.g. "timocom").
            scopes: List of allowed scope strings.
            created_by: User ID who created this key (0 = system).
            expires_at: ISO-8601 expiry timestamp, or ``None`` for no expiry.

        Returns:
            ``(plaintext_key, key_id)``
        """
        raw_key = f"ok_{secrets.token_hex(24)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:12]
        scopes_str = json.dumps(scopes or [])

        data = {
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "name": name,
            "partner": partner,
            "scopes": scopes_str,
            "is_active": 1,
            "created_by": created_by,
            "expires_at": expires_at,
            "company_id": self._user_company_id or 0,
        }
        self._validate_columns(data, extra_allowed={"company_id"})

        key_id = self._execute_insert(
            f"INSERT INTO {self.TABLE} "
            f"(key_hash, key_prefix, name, partner, scopes, "
            f"is_active, created_by, expires_at, company_id) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                key_hash,
                key_prefix,
                name,
                partner,
                scopes_str,
                1,
                created_by,
                expires_at,
                self._user_company_id or 0,
            ), commit=True,
		)
        logger.info("Created API key '%s' for partner '%s' (id=%d)", name, partner, key_id)
        return raw_key, key_id

    def validate_key(self, raw_key: str) -> Optional[Dict[str, Any]]:
        """Validate an API key and return its metadata dict if valid.

        Also updates ``last_used_at`` to the current timestamp.

        Returns ``None`` if the key is unknown, inactive, or expired.
        """
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        # key_hash is UNIQUE globally — no company filter needed here
        # because external callers have no user session context.
        row = self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE key_hash = ? AND is_active = 1",
            (key_hash,),
        )
        if not row:
            return None

        # ── Check expiry ───────────────────────────────────────────────
        expires = row.get("expires_at")
        if expires:
            try:
                expiry_dt = datetime.fromisoformat(expires)
                if expiry_dt < datetime.now():
                    logger.info("API key '%s' expired at %s", row["name"], expires)
                    return None
            except (ValueError, TypeError):
                logger.warning("API key '%s' has unparseable expires_at: %s", row["name"], expires)

        # ── Update last_used_at ────────────────────────────────────────
        self._execute(
            f"UPDATE {self.TABLE} SET last_used_at = datetime('now') WHERE id = ?",
            (row["id"],), commit=True,
		)

        return dict(row)

    def revoke_key(self, key_id: int) -> bool:
        """Soft-delete / revoke an API key by id.

        Only the owning company can revoke their own keys (enforced via
        the company filter for non-admin users).
        """
        affected = self._execute_with_count(
            f"UPDATE {self.TABLE} "
            f"SET is_active = 0, revoked_at = datetime('now') "
            f"WHERE id = ? {self._company_filter()}",
            (key_id,) + self._company_params(), commit=True,
		)
        if affected:
            logger.info("Revoked API key id=%d", key_id)
            return True
        logger.warning("No API key found to revoke with id=%d", key_id)
        return False

    # ── Query helpers ──────────────────────────────────────────────────

    def list_keys(self, partner: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all API keys, optionally filtered by partner slug.

        Results are ordered by creation date descending.
        Scoped users see only their company's keys; admins see all.
        """
        select_cols = (
            "id, key_prefix, name, partner, scopes, is_active, "
            "created_by, created_at, last_used_at, expires_at, revoked_at"
        )
        if partner:
            return self._fetchall(
                f"SELECT {select_cols} FROM {self.TABLE} "
                f"WHERE partner = ? {self._company_filter()} "
                f"ORDER BY created_at DESC",
                (partner,) + self._company_params(),
            )
        return self._fetchall(
            f"SELECT {select_cols} FROM {self.TABLE} "
            f"WHERE 1=1 {self._company_filter()} "
            f"ORDER BY created_at DESC",
            self._company_params(),
        )

    def get_by_id(self, key_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single key by its id."""
        return self._fetchone(
            f"SELECT * FROM {self.TABLE} WHERE id = ? {self._company_filter()}",
            (key_id,) + self._company_params(),
        )
