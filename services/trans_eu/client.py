"""Low-level HTTP client for Trans.eu Platform API.

Handles OAuth token exchange, Api-key header injection, and raw
request/response handling. Used by TransEuAdapter and other
Trans.eu domain services.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
TRANS_EU_AUTH_BASE = "https://auth.platform.trans.eu"
TRANS_EU_API_BASE = "https://api.platform.trans.eu/ext"
TRANS_EU_TOKEN_ENDPOINT = "/auth-api/accounts/token"
TRANS_EU_FREIGHTS_ENDPOINT = "/freights-api/v1/freights"
TRANS_EU_FREIGHT_DETAIL_ENDPOINT = "/freights-api/v1/freights/{freight_id}"
TRANS_EU_ACCEPTED_FREIGHTS_ENDPOINT = "/freights-api/v1/accepted"
TRANS_EU_ARCHIVE_ENDPOINT = "/freights-api/v1/archive"

TRANS_EU_EXCHANGE_PUB_ENDPOINT = "/freights-api/v1/freight-exchange"
TRANS_EU_PRIVATE_EXCHANGE_PUB_ENDPOINT = "/freights-api/v1/private-exchange"
TRANS_EU_CORPORATE_PUB_ENDPOINT = "/freights-api/v1/freight-corporate"
TRANS_EU_COMPANIES_PUB_ENDPOINT = "/freights-api/v1/freight-companies"
TRANS_EU_EMPLOYEES_PUB_ENDPOINT = "/freights-api/v1/freight-employees"
TRANS_EU_AUTO_PUB_ENDPOINT = "/freights-api/v1/freight-auto"

TRANS_EU_OFFERS_ENDPOINT = "/freights-api/v1/freights/{freight_id}/offers"
TRANS_EU_OFFER_DETAIL_ENDPOINT = "/freights-api/v1/freights/offers/{offer_id}"
TRANS_EU_ORDERS_CREATED_ENDPOINT = "/orders-api/v1/orders-created"

DEFAULT_TIMEOUT = 30


class TransEuAPIError(Exception):
    """Base error for Trans.eu API failures."""
    def __init__(self, message: str, status_code: int = 0, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class TransEuAuthError(TransEuAPIError):
    """Authentication/authorization error (401)."""


class TransEuRateLimitError(TransEuAPIError):
    """Rate limit exceeded (429)."""


class TransEuClient:
    """Low-level HTTP client wrapping the Trans.eu Platform API.

    Injects Api-key and Authorization headers on every request.
    Used by TransEuAdapter and domain services.

    Usage::

        client = TransEuClient(api_key="...")
        # Exchange OAuth code for tokens
        tokens = await client.exchange_code_for_token(
            code="...", redirect_uri="...", client_id="...", client_secret="..."
        )
        # Make authenticated request
        data = await client.get(access_token="...", path="/freights-api/v1/freights")
    """

    def __init__(self, api_key: str):
        self._api_key = api_key

    # ── OAuth Token Operations ──────────────────────────────────────

    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
    ) -> dict:
        """Exchange OAuth authorization_code for access_token + refresh_token.

        POST /ext/auth-api/accounts/token with grant_type=authorization_code.
        """
        return await self._post_token({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        })

    async def refresh_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict:
        """Refresh an access token using a refresh_token.

        POST /ext/auth-api/accounts/token with grant_type=refresh_token.
        """
        return await self._post_token({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })

    async def _post_token(self, data: dict) -> dict:
        """Internal: POST to the token endpoint."""
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.post(
                f"{TRANS_EU_API_BASE}{TRANS_EU_TOKEN_ENDPOINT}",
                data=data,
                headers={
                    "Api-key": self._api_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            self._handle_response(resp)
            return resp.json()

    # ── Authenticated HTTP Methods ──────────────────────────────────

    async def get(
        self, access_token: str, path: str, params: dict = None
    ) -> dict:
        """GET request to Trans.eu API with Bearer token + Api-key."""
        return await self._request("GET", access_token, path, params=params)

    async def post(
        self, access_token: str, path: str, json_data: dict = None
    ) -> dict:
        """POST request to Trans.eu API with Bearer token + Api-key."""
        return await self._request("POST", access_token, path, json_data=json_data)

    async def put(
        self, access_token: str, path: str, json_data: dict = None
    ) -> dict:
        """PUT request to Trans.eu API with Bearer token + Api-key."""
        return await self._request("PUT", access_token, path, json_data=json_data)

    async def patch(
        self, access_token: str, path: str, json_data: dict = None
    ) -> dict:
        """PATCH request to Trans.eu API with Bearer token + Api-key."""
        return await self._request("PATCH", access_token, path, json_data=json_data)

    async def delete(
        self, access_token: str, path: str
    ) -> dict:
        """DELETE request to Trans.eu API with Bearer token + Api-key."""
        return await self._request("DELETE", access_token, path)

    async def _request(
        self,
        method: str,
        access_token: str,
        path: str,
        params: dict = None,
        json_data: dict = None,
    ) -> dict:
        """Make an authenticated request to the Trans.eu API."""
        url = f"{TRANS_EU_API_BASE}{path}" if path.startswith("/") else path

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Api-key": self._api_key,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data if method in ("POST", "PUT", "PATCH") else None,
            )
            self._handle_response(resp)
            return resp.json() if resp.content else {}

    # ── Helpers ─────────────────────────────────────────────────────

    def build_auth_url(self, client_id: str, redirect_uri: str, state: str) -> str:
        """Build the OAuth authorization URL for user login."""
        return (
            f"{TRANS_EU_AUTH_BASE}/oauth2/auth?"
            f"client_id={client_id}&response_type=code&"
            f"redirect_uri={redirect_uri}&state={state}"
        )

    @staticmethod
    def _handle_response(resp: httpx.Response) -> None:
        """Raise appropriate error for non-2xx responses."""
        if resp.status_code == 401:
            raise TransEuAuthError(
                f"Trans.eu authentication failed (401): {resp.text[:500]}",
                status_code=401,
                response_body=resp.text,
            )
        if resp.status_code == 429:
            raise TransEuRateLimitError(
                f"Trans.eu rate limit exceeded (429)",
                status_code=429,
                response_body=resp.text,
            )
        if resp.status_code >= 400:
            raise TransEuAPIError(
                f"Trans.eu API error ({resp.status_code}): {resp.text[:500]}",
                status_code=resp.status_code,
                response_body=resp.text,
            )
