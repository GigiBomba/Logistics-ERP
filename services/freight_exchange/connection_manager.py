"""Freight Exchange connection manager — session lifecycle and health checks.

Provides ``ConnectionManagerService`` which wraps the registry and repository
to manage per-company, per-provider sessions, authentication, health probing,
connect/disconnect lifecycle, and provider listing.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from models.freight_exchange_models import (
    ProviderCredentials,
    ProviderHealthCheck,
    ProviderSession,
)
from repositories.freight_exchange_repository import FreightExchangeRepository
from services.freight_exchange.registry import get_adapter

logger = logging.getLogger(__name__)


class ConnectionManagerService:
    """Manages freight exchange provider connections and health checks.

    Wraps the adapter registry and the freight exchange repository to
    provide a unified interface for session lifecycle, health probing,
    connection management, and provider listing.
    """

    def __init__(self, db):
        self.db = db
        self.repo = FreightExchangeRepository(db)

    # ── Connection Lifecycle ───────────────────────────────────────────

    async def connect_provider(
        self, company_id: int, provider_id: str, credentials: ProviderCredentials
    ) -> dict:
        """Connect a company to a freight exchange provider.

        Authenticates, stores credentials + session, returns connection info.
        Upserts if a connection already exists for this (company, provider).
        """
        adapter = get_adapter(provider_id)
        if adapter is None:
            raise ValueError(f"Unknown provider: {provider_id}")

        session = await adapter.authenticate(credentials)
        now = datetime.now(timezone.utc).isoformat()

        data = {
            "company_id": company_id,
            "provider_id": provider_id,
            "credentials_encrypted": credentials.client_secret_encrypted,
            "session_state": json.dumps(session.model_dump(mode="json")),
            "status": "connected",
            "connected_at": now,
            "created_at": now,
            "last_health_check_status": "healthy",
            "last_health_check_at": now,
        }
        if session.user_id is not None:
            data["user_id"] = session.user_id

        existing = self.repo.get_connection(company_id, provider_id)
        if existing:
            del data["created_at"]
            self.repo.update_connection(existing["id"], data)
            logger.info("Reconnected company %d to provider '%s'", company_id, provider_id)
            return {"connection_id": existing["id"], "status": "connected"}
        else:
            try:
                conn_id = self.repo.create_connection(data)
                logger.info("Connected company %d to provider '%s' (id=%s)", company_id, provider_id, conn_id)
                return {"connection_id": conn_id, "status": "connected"}
            except Exception:
                # Race: another request created the connection between our check and insert
                existing = self.repo.get_connection(company_id, provider_id)
                if existing:
                    del data["created_at"]
                    self.repo.update_connection(existing["id"], data)
                    logger.info("Reconnected company %d to provider '%s' (race resolved)", company_id, provider_id)
                    return {"connection_id": existing["id"], "status": "connected"}
                raise

    async def disconnect_provider(self, company_id: int, provider_id: str) -> None:
        """Disconnect a company from a provider."""
        existing = self.repo.get_connection(company_id, provider_id)
        if existing:
            self.repo.update_connection(
                existing["id"],
                {"status": "disconnected", "session_state": None},
            )
            logger.info("Disconnected company %d from provider '%s'", company_id, provider_id)

    # ── Session Management ─────────────────────────────────────────────

    async def get_session(
        self, company_id: int, provider_id: str
    ) -> Optional[ProviderSession]:
        """Return an active, refreshed session for the given connection.

        If the session token is expired, transparently refreshes it.
        Returns None if the connection doesn't exist or is disconnected.
        """
        row = self.repo.get_connection(company_id, provider_id)
        if not row or row.get("status") != "connected":
            return None

        session = self._deserialise_session(row, company_id, provider_id)
        if session is None:
            return None

        adapter = get_adapter(provider_id)
        if adapter is None:
            return None

        try:
            session = await adapter.refresh_session(session)
            self.repo.update_connection(
                row["id"],
                {"session_state": json.dumps(session.model_dump(mode="json"))},
            )
        except Exception:
            logger.warning(
                "Session refresh failed for company %d / provider '%s'",
                company_id, provider_id,
            )
            return None

        return session

    def get_active_session_sync(
        self, company_id: int, provider_id: str
    ) -> Optional[ProviderSession]:
        """Synchronous helper — returns session as-stored (no refresh)."""
        row = self.repo.get_connection(company_id, provider_id)
        if not row or row.get("status") != "connected":
            return None
        return self._deserialise_session(row, company_id, provider_id)

    # ── Health ─────────────────────────────────────────────────────────

    async def test_connection(
        self, company_id: int, provider_id: str
    ) -> Optional[ProviderHealthCheck]:
        """Ping a single provider and persist the health result."""
        connection = self.repo.get_connection(company_id, provider_id)
        if connection is None:
            logger.warning("No connection for company=%d provider=%s", company_id, provider_id)
            return None

        adapter = get_adapter(provider_id)
        if adapter is None:
            logger.warning("No adapter for provider=%s", provider_id)
            return None

        session = self._deserialise_session(connection, company_id, provider_id)
        if session is None:
            return None

        try:
            health = await adapter.test_connection(session)
        except Exception as exc:
            logger.error("test_connection raised for company=%d provider=%s: %s", company_id, provider_id, exc)
            health = ProviderHealthCheck(
                provider_id=provider_id, status="down", latency_ms=0,
                checked_at=datetime.now(timezone.utc), error=str(exc),
            )

        connection_id = str(connection["id"])
        try:
            self.repo.update_health(connection_id, health.status, health.checked_at.isoformat())
        except Exception as exc:
            logger.error("Failed to persist health for connection %s: %s", connection_id, exc)

        return health

    # ── Listing ────────────────────────────────────────────────────────

    def list_connected_providers(self, company_id: int) -> list[dict]:
        """Return all providers with connection status for a company."""
        connections = self.repo.list_connections(company_id)
        result = []
        for row in connections:
            session = self._deserialise_session(row, company_id, row.get("provider_id", ""))
            caps = self._get_capabilities(row.get("provider_id", ""))
            result.append({
                "connection_id": row["id"],
                "provider_id": row["provider_id"],
                "status": row.get("status", "disconnected"),
                "connected_at": row.get("connected_at"),
                "last_health_check_at": row.get("last_health_check_at"),
                "last_health_check_status": row.get("last_health_check_status"),
                "session_expires_at": session.expires_at.isoformat() if session else None,
                "capabilities": caps,
            })
        return result

    def list_connected_provider_ids(self, company_id: int) -> list[str]:
        """Return provider_ids that are connected and not known-down."""
        rows = self.repo.get_connected_providers(company_id)
        return [
            r["provider_id"]
            for r in rows
            if r.get("last_health_check_status") != "down"
        ]

    def is_connected(self, company_id: int, provider_id: str) -> bool:
        """Check if a company has an active connection to a provider."""
        row = self.repo.get_connection(company_id, provider_id)
        return row is not None and row.get("status") == "connected"

    # ── Trans.eu User Token Management ───────────────────────────────

    async def connect_trans_eu_user(
        self, company_id: int, user_id: int, credentials: ProviderCredentials
    ) -> ProviderSession:
        """Connect a specific user to Trans.eu via OAuth authorization_code.

        Exchanges the authorization_code for tokens, stores the encrypted
        tokens in trans_eu_user_tokens via the repository, and returns a
        ProviderSession with user_id set.
        """
        adapter = get_adapter("trans_eu")
        if adapter is None:
            raise ValueError("Trans.eu adapter not registered")

        # Set user context on credentials (for session.user_id to be populated)
        credentials.company_id = company_id
        session = await adapter.authenticate(credentials)
        session.user_id = user_id   # attach user context

        # Store with user_id in the connection
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "company_id": company_id,
            "provider_id": "trans_eu",
            "user_id": user_id,
            "credentials_encrypted": credentials.client_secret_encrypted,
            "session_state": json.dumps(session.model_dump(mode="json")),
            "status": "connected",
            "connected_at": now,
            "created_at": now,
            "last_health_check_status": "healthy",
            "last_health_check_at": now,
        }

        existing = self.repo.get_connection(company_id, "trans_eu")
        if existing:
            del data["created_at"]
            self.repo.update_connection(existing["id"], data)
            logger.info("Reconnected user %d to Trans.eu (company %d)", user_id, company_id)
        else:
            try:
                self.repo.create_connection(data)
                logger.info("Connected user %d to Trans.eu (company %d)", user_id, company_id)
            except Exception:
                existing = self.repo.get_connection(company_id, "trans_eu")
                if existing:
                    del data["created_at"]
                    self.repo.update_connection(existing["id"], data)
                else:
                    raise

        return session

    def get_trans_eu_session_for_user(
        self, company_id: int, user_id: int
    ) -> Optional[ProviderSession]:
        """Return the Trans.eu session for a specific user within a company.

        Returns None if no session exists for this user, the connection
        is disconnected, or deserialization fails.
        """
        row = self.repo.get_connection(company_id, "trans_eu")
        if not row or row.get("status") != "connected":
            return None
        if row.get("user_id") != user_id:
            logger.debug(
                "Trans.eu connection exists for company=%d but belongs to user_id=%d, not %d",
                company_id, row.get("user_id"), user_id,
            )
            return None
        return self._deserialise_session(row, company_id, "trans_eu")

    # ── Private helpers ────────────────────────────────────────────────

    def _deserialise_session(
        self, connection: dict, company_id: int, provider_id: str
    ) -> Optional[ProviderSession]:
        """Rebuild a ProviderSession from the stored connection row."""
        raw = connection.get("session_state")
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return ProviderSession(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Malformed session_state for company=%d provider=%s: %s", company_id, provider_id, exc)
            return None

    def _get_capabilities(self, provider_id: str) -> Optional[dict]:
        """Get provider capabilities, serialized for API response."""
        adapter = get_adapter(provider_id)
        if adapter is None:
            return None
        caps = adapter.capabilities()
        return caps.model_dump() if caps else None
