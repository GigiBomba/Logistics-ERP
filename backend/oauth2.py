"""OAuth2 client credentials grant implementation."""
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from backend.dependencies import get_request_company_id
from backend.security import create_access_token

logger = logging.getLogger(__name__)


@dataclass
class OAuth2Client:
    """Registered OAuth2 client."""
    client_id: str
    client_name: str
    partner: str
    scopes: list[str]
    is_active: bool
    created_at: str
    last_used_at: Optional[str] = None


class OAuth2Service:
    """OAuth2 client credentials grant service."""

    def __init__(self, db):
        self.db = db

    def register_client(
        self, name: str, partner: str, scopes: list[str],
        user_id: int = 0,
    ) -> tuple[str, str]:
        """Register a new OAuth2 client. Returns (client_id, client_secret).

        The client_secret is returned only once at creation time.
        Only the SHA-256 hash is stored.
        """
        client_id = f"operion_{secrets.token_hex(12)}"  # operion_ + 24 chars
        client_secret = secrets.token_hex(32)  # 64 chars
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        self.db.conn.execute(
            """INSERT INTO oauth2_clients
               (client_id, client_name, partner, scopes, secret_hash,
                is_active, created_by, company_id)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            (client_id, name, partner, str(scopes), secret_hash, user_id,
             self._get_company_id()),
        )
        self.db.conn.commit()
        logger.info(
            "Registered OAuth2 client '%s' for partner '%s' (id=%s)",
            name, partner, client_id,
        )
        return client_id, client_secret

    def validate_client(
        self, client_id: str, client_secret: str,
    ) -> Optional[OAuth2Client]:
        """Validate client credentials. Returns client info if valid."""
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

        row = self.db.conn.execute(
            """SELECT * FROM oauth2_clients
               WHERE client_id = ? AND secret_hash = ? AND is_active = 1""",
            (client_id, secret_hash),
        ).fetchone()

        if not row:
            return None

        # Update last_used_at
        self.db.conn.execute(
            "UPDATE oauth2_clients SET last_used_at = ? WHERE client_id = ?",
            (datetime.now().isoformat(), client_id),
        )
        self.db.conn.commit()

        return OAuth2Client(
            client_id=row["client_id"],
            client_name=row["client_name"],
            partner=row["partner"],
            scopes=json.loads(row["scopes"] or "[]") if isinstance(row["scopes"], str) else list(row["scopes"] or []),
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            last_used_at=row.get("last_used_at"),
        )

    def issue_token(
        self, client_id: str, client_secret: str, scope: str = "",
    ) -> Optional[dict]:
        """Validate client credentials and return a JWT token dict if valid.

        Returns None if credentials are invalid.
        Otherwise returns the standard OAuth2 token response dict.
        """
        client = self.validate_client(client_id, client_secret)
        if not client:
            return None

        requested_scopes = scope.split() if scope else client.scopes

        access_token = create_access_token(
            data={
                "sub": client.client_id,
                "type": "client_credentials",
                "client_name": client.client_name,
                "partner": client.partner,
                "scopes": requested_scopes,
            },
            expires_delta=timedelta(hours=1),
        )

        logger.info(
            "OAuth2 client credentials token issued: %s (partner=%s)",
            client.client_id, client.partner,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",  # nosec B105
            "expires_in": 3600,
            "scope": " ".join(requested_scopes),
        }

    def revoke_client(self, client_id: str) -> None:
        """Revoke an OAuth2 client."""
        self.db.conn.execute(
            "UPDATE oauth2_clients SET is_active = 0 WHERE client_id = ?",
            (client_id,),
        )
        self.db.conn.commit()
        logger.info("Revoked OAuth2 client: %s", client_id)

    def list_clients(self, partner: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered OAuth2 clients scoped to the current company."""
        company_id = self._get_company_id()
        if partner:
            rows = self.db.conn.execute(
                """SELECT client_id, client_name, partner, scopes,
                          is_active, created_at, last_used_at
                   FROM oauth2_clients
                   WHERE partner = ? AND oauth2_clients.company_id = ?
                   ORDER BY created_at DESC""",
                (partner, company_id),
            ).fetchall()
        else:
            rows = self.db.conn.execute(
                """SELECT client_id, client_name, partner, scopes,
                          is_active, created_at, last_used_at
                   FROM oauth2_clients
                   WHERE oauth2_clients.company_id = ?
                   ORDER BY created_at DESC""",
                (company_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _get_company_id() -> int:
        return get_request_company_id() or 0
