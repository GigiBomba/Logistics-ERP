from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from client.auth import Auth
from client.config import ClientConfig, get_client_config

logger = logging.getLogger(__name__)

_default_config: Optional[ClientConfig] = None


class PdfWithRecord(bytes):
    """PDF bytes that also carry the server-assigned record.

    Subclasses ``bytes`` so existing callers (which treat the result as raw
    PDF data) keep working unchanged, while the assigned record is surfaced
    as ``result.record`` (e.g. ``{"invoice_number": "INV-2026-0042",
    "id": 12}``) when the server included it in the response headers.
    """

    def __new__(cls, content: bytes, record: Optional[Dict[str, Any]] = None):
        obj = super().__new__(cls, content)
        obj.record = record or {}
        return obj


class ApiClient:
    def __init__(self, base_url: Optional[str] = None,
                 verify_ssl: Optional[bool] = None,
                 config: Optional[ClientConfig] = None,
                 api_key: Optional[str] = None,
                 auth: Optional[Auth] = None):
        if config is not None:
            self._config = config
            self._base_url = base_url or config.api_url
            self._verify_ssl = verify_ssl if verify_ssl is not None else config.verify_ssl
            self._api_key = api_key or config.api_key
        else:
            self._config = get_client_config()
            self._base_url = base_url or self._config.api_url
            self._verify_ssl = verify_ssl if verify_ssl is not None else self._config.verify_ssl
            self._api_key = api_key or self._config.api_key
        self._auth: Optional[Auth] = auth
        headers: Dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if self._auth is not None and self._auth.token is not None:
            headers.update(self._auth.headers)
        self._client = httpx.Client(
            timeout=30.0, verify=self._verify_ssl, headers=headers,
            follow_redirects=True,
        )
        self._online: Optional[bool] = None
        self._consecutive_transient_failures: int = 0
        self._circuit_open_until: float = 0.0

    def update_auth(self, auth: Auth) -> None:
        """Update or set the auth token after construction.

        Called after a fresh login or token refresh so the http client's
        ``Authorization`` header reflects the new credentials.  Passing
        ``None`` (or an auth without a token — logout / cleared session)
        REMOVES any stale ``Authorization`` header: a client that keeps
        sending a dead token would 401 on every request forever.
        """
        self._auth = auth
        if auth is not None and auth.token is not None:
            self._client.headers.update(auth.headers)
        else:
            self._client.headers.pop("Authorization", None)

    def is_online(self) -> bool:
        if self._online is None:
            try:
                resp = self._client.get(f"{self._base_url}/api/v1/health/")
                self._online = resp.status_code == 200
            except Exception:
                self._online = False
        return self._online

    def get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Public GET returning parsed JSON (used by the sync pull lane)."""
        return self._get(path, params=params)

    def post(self, path: str, json: Optional[Dict] = None) -> Dict[str, Any]:
        """Public POST returning parsed JSON (used by the sync push lane).

        Wraps the private ``_post`` so the sync engine (and other callers)
        can POST without reaching into the underscore-prefixed API.
        """
        return self._post(path, json_data=json)

    # ── Infrastructure helpers ─────────────────────────────────────────

    def _check_response(self, resp: httpx.Response) -> bool:
        """Check for 401 — attempt token refresh before clearing auth.

        If the response is 401 and the ``Auth`` instance has a refresh
        token, this method tries to silently refresh the access token
        via ``POST /auth/refresh``.  If the refresh succeeds, the client
        headers are updated and the caller is expected to retry.

        Returns:
            ``True`` if the caller should retry the original request
            (token was refreshed), ``False`` if the auth state was cleared.
        """
        if resp.status_code == 401 and self._auth is not None:
            if self._auth.refresh_token:
                logger.info("Received 401 — attempting silent token refresh.")
                refreshed = self._auth.refresh()
                if refreshed:
                    # Update the httpx client Bearer header
                    self._client.headers.update(self._auth.headers)
                    logger.info("Token refreshed — caller should retry.")
                    return True
            # No refresh token or refresh failed — clear auth
            logger.info("Token refresh failed — clearing auth state.")
            self._auth.clear_token()
            # Drop the stale Bearer header too — otherwise the client keeps
            # sending the dead token and 401s on every subsequent request.
            self._client.headers.pop("Authorization", None)
            from client.auth_manager import clear_auth
            clear_auth()
        return False

    _TRANSIENT_STATUSES = {502, 503, 504}
    _CIRCUIT_BREAKER_THRESHOLD = 5   # consecutive transient failures before opening
    _CIRCUIT_BREAKER_COOLDOWN = 30   # seconds to stay open before half-open probe

    def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an HTTP request with exponential backoff retry (up to 3 attempts).

        Retries on connection errors AND transient server errors (502, 503, 504).

        Includes a circuit breaker: after N consecutive transient failures,
        the client enters an open state and fails fast for a cooldown period
        instead of blocking the caller with repeated retries.
        """
        max_attempts = 3
        last_exc: Optional[Exception] = None
        last_resp: Optional[httpx.Response] = None

        # ── Circuit breaker: fail fast if the API is known to be down ──
        if self._circuit_open_until > time.monotonic():
            remaining = int(self._circuit_open_until - time.monotonic())
            logger.debug(
                "Circuit breaker OPEN — skipping %s %s (cooldown %ds remaining)",
                method.upper(), url, remaining,
            )
            raise RuntimeError(
                f"API server is down (circuit breaker open, "
                f"{remaining}s remaining)"
            )

        for attempt in range(max_attempts):
            try:
                resp = self._client.request(method, url, **kwargs)
                if self._check_response(resp):
                    resp = self._client.request(method, url, **kwargs)

                # Retry on transient server errors (gateway timeouts, etc.)
                if resp.status_code in self._TRANSIENT_STATUSES and attempt < max_attempts - 1:
                    last_resp = resp
                    self._consecutive_transient_failures += 1
                    # Open circuit breaker after too many consecutive transient failures
                    if self._consecutive_transient_failures >= self._CIRCUIT_BREAKER_THRESHOLD:
                        self._circuit_open_until = time.monotonic() + self._CIRCUIT_BREAKER_COOLDOWN
                        logger.warning(
                            "Circuit breaker OPEN after %d consecutive transient failures "
                            "— API server appears down, skipping retries for %ds",
                            self._consecutive_transient_failures,
                            self._CIRCUIT_BREAKER_COOLDOWN,
                        )
                        if last_resp is not None:
                            return last_resp
                        raise RuntimeError(
                            "API server is down (circuit breaker open)"
                        )
                    logger.warning(
                        "Transient server error %s on %s %s — retrying (%d/%d)",
                        resp.status_code, method.upper(), url, attempt + 1, max_attempts,
                    )
                    time.sleep(2 ** attempt)
                    continue

                # Successful response — reset circuit breaker
                self._consecutive_transient_failures = 0
                self._circuit_open_until = 0.0
                return resp

            except (httpx.ConnectError, httpx.TimeoutException,
                    httpx.RemoteProtocolError, httpx.ReadError) as exc:
                last_exc = exc
                self._consecutive_transient_failures += 1
                if self._consecutive_transient_failures >= self._CIRCUIT_BREAKER_THRESHOLD:
                    self._circuit_open_until = time.monotonic() + self._CIRCUIT_BREAKER_COOLDOWN
                    logger.warning(
                        "Circuit breaker OPEN after %d consecutive connection failures — "
                        "cooldown for %ds",
                        self._consecutive_transient_failures,
                        self._CIRCUIT_BREAKER_COOLDOWN,
                    )
                    raise RuntimeError(
                        "API server is down (circuit breaker open)"
                    ) from last_exc
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                continue
        if last_resp is not None:
            return last_resp  # Allow raise_for_status to propagate the final 502
        raise RuntimeError(
            f"API server unreachable at {self._base_url}: {last_exc}"
        ) from last_exc

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        resp = self._request_with_retry("GET", f"{self._base_url}{path}", params=params)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.warning("Non-JSON response from %s: %s", path, getattr(resp, "text", ""))
            return {"detail": "Invalid JSON response from server"}

    def _post(
        self, path: str, json_data: Optional[Dict] = None,
        files: Optional[Dict] = None, data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        resp = self._request_with_retry(
            "POST", f"{self._base_url}{path}",
            json=json_data, files=files, data=data,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.warning("Non-JSON response from POST %s: %s", path, getattr(resp, "text", ""))
            return {"detail": "Invalid JSON response from server"}

    def _put(self, path: str, json_data: Dict) -> Dict[str, Any]:
        resp = self._request_with_retry("PUT", f"{self._base_url}{path}", json=json_data)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.warning("Non-JSON response from PUT %s: %s", path, getattr(resp, "text", ""))
            return {"detail": "Invalid JSON response from server"}

    def _patch(self, path: str, json_data: Dict) -> Dict[str, Any]:
        resp = self._request_with_retry("PATCH", f"{self._base_url}{path}", json=json_data)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.warning("Non-JSON response from PATCH %s: %s", path, getattr(resp, "text", ""))
            return {"detail": "Invalid JSON response from server"}

    def _delete(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        resp = self._request_with_retry("DELETE", f"{self._base_url}{path}", params=params)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            logger.warning("Non-JSON response from DELETE %s: %s", path, getattr(resp, "text", ""))
            return {"detail": "Invalid JSON response from server"}

    def _download(self, path: str, params: Optional[Dict] = None) -> bytes:
        """GET a binary response (PDF, XLSX) and return raw bytes."""
        resp = self._request_with_retry("GET", f"{self._base_url}{path}", params=params)
        resp.raise_for_status()
        return resp.content

    def _post_binary(self, path: str, json_data: Dict) -> bytes:
        """POST returning raw bytes (PDF/XLSX) with auth retry support."""
        resp = self._request_with_retry("POST", f"{self._base_url}{path}", json=json_data)
        resp.raise_for_status()
        return resp.content

    @staticmethod
    def _clean_params(**kwargs: Any) -> Dict[str, Any]:
        """Strip None and empty-string values from query params."""
        return {k: v for k, v in kwargs.items() if v is not None and v != ""}

    # ── Document endpoints ────────────────────────────────────────────

    def list_documents(
        self, query: str = "", category: str = "", entity_type: str = "",
        date_from: str = "", date_to: str = "", mime_type: str = "",
        order: str = "uploaded_at DESC", page: int = 0, page_size: int = 20,
    ) -> Dict[str, Any]:
        return self._get("/api/v1/documents/", params=self._clean_params(
            query=query, category=category, entity_type=entity_type,
            date_from=date_from, date_to=date_to, mime_type=mime_type,
            order=order, page=page, page_size=page_size,
        ))

    def get_document(self, doc_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/documents/{doc_id}")

    def read_document_info(self, doc_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/documents/{doc_id}/read")

    def upload_document(
        self, file_path: str, category: str = "",
        entity_type: str = "", entity_id: Optional[int] = None,
        uploaded_by: str = "user",
    ) -> Dict[str, Any]:
        # R4: read the bytes up front — passing an open handle means a retry
        # (transient 5xx / 401-refresh) re-sends an exhausted file → the
        # server stores an empty file.
        with open(file_path, "rb") as f:
            content = f.read()
        files = {"file": (os.path.basename(file_path), content)}
        data = {
            "category": category, "entity_type": entity_type,
            "entity_id": str(entity_id or ""), "uploaded_by": uploaded_by,
        }
        return self._post("/api/v1/documents/upload", files=files, data=data)

    def update_document(self, doc_id: int, **fields: Any) -> Dict[str, Any]:
        return self._put(f"/api/v1/documents/{doc_id}", json_data=fields)

    def delete_document(self, doc_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/documents/{doc_id}")

    def upload_document_file(
        self, doc_id: int, file_path: str, skip_ocr: bool = False,
    ) -> Dict[str, Any]:
        """Upload a document's binary file to an existing server document (Phase C).

        ``skip_ocr`` suppresses server-side OCR (the sync lane sets it — the
        desktop's OCR text is already carried by the row sync).
        """
        # R4: read the bytes up front so a retry (transient 5xx / 401-refresh)
        # does NOT re-send an exhausted file handle (empty upload).  Size-capped
        # to the server's 50 MB limit; the server is the authoritative check.
        with open(file_path, "rb") as f:
            content = f.read()
        if len(content) > 50 * 1024 * 1024:
            raise ValueError(
                f"File too large to upload: {len(content)} bytes (max 50 MB)"
            )
        data = {"skip_ocr": "true" if skip_ocr else "false"}
        return self._post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": (os.path.basename(file_path), content)},
            data=data,
        )

    def download_document_file(self, doc_id: int, dest_path: str) -> str:
        """Download a document's binary file to *dest_path* (Phase C)."""
        content = self._download(f"/api/v1/documents/{doc_id}/file")
        parent = os.path.dirname(os.path.abspath(dest_path))
        os.makedirs(parent, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(content)
        return dest_path

    def link_document(
        self, doc_id: int, entity_type: str, entity_id: int,
        relation_type: str = "attached",
    ) -> Dict[str, Any]:
        return self._post(f"/api/v1/documents/{doc_id}/links", json_data={
            "linked_entity_type": entity_type,
            "linked_entity_id": entity_id,
            "relation_type": relation_type,
        })

    def add_document_tag(self, doc_id: int, tag: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/documents/{doc_id}/tags", data={"tag": tag})

    def remove_document_tag(self, doc_id: int, tag: str) -> Dict[str, Any]:
        return self._delete(f"/api/v1/documents/{doc_id}/tags/{tag}")

    def get_document_links(self, doc_id: int) -> List[Dict[str, Any]]:
        result = self._get(f"/api/v1/documents/{doc_id}/links")
        return result if isinstance(result, list) else []

    def get_document_versions(self, doc_id: int) -> List[Dict[str, Any]]:
        result = self._get(f"/api/v1/documents/{doc_id}/versions")
        return result if isinstance(result, list) else []

    def get_document_categories(self) -> List[Dict[str, Any]]:
        result = self._get("/api/v1/documents/categories")
        return result if isinstance(result, list) else []

    # ── OCR endpoints ─────────────────────────────────────────────────

    def run_ocr(self, document_id: int, engine: str = "auto") -> Dict[str, Any]:
        return self._post("/api/v1/ocr/run", json_data={
            "document_id": document_id, "engine": engine,
        })

    def get_ocr_status(self, doc_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/ocr/status/{doc_id}")

    # ── Trip endpoints ────────────────────────────────────────────────

    def list_trips(self, search: str = "", status: str = "", limit: int = 200) -> Dict[str, Any]:
        return self._get("/api/v1/trips/", params=self._clean_params(
            search=search, status=status, limit=limit,
        ))

    def get_top_trucks_by_revenue(self, month_start: str, month_end: str, limit: int = 4) -> Dict[str, Any]:
        return self._get("/api/v1/trips/top-trucks", params=self._clean_params(
            month_start=month_start, month_end=month_end, limit=limit,
        ))

    def get_trip(self, trip_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/trips/{trip_id}")

    def create_trip(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/api/v1/trips/", json_data=data)

    def update_trip(self, trip_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._put(f"/api/v1/trips/{trip_id}", json_data=data)

    def delete_trip(self, trip_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/trips/{trip_id}")

    def check_trip_conflicts(self, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/api/v1/trips/conflicts/check", json_data=trip_data)

    def export_trip_pdf(self, trip_id: int) -> bytes:
        return self._download(f"/api/v1/trips/{trip_id}/export/pdf")

    def export_trip_xlsx(self, trip_id: int) -> bytes:
        return self._download(f"/api/v1/trips/{trip_id}/export/xlsx")

    # ── Client endpoints ──────────────────────────────────────────────

    def list_clients(self, query: str = "", limit: int = 200,
                     include_inactive: bool = False,
                     page: int = 1,
                     page_size: int | None = None) -> Dict[str, Any]:
        # The backend caps page_size at 200; send it explicitly so search
        # results respect the requested limit (the backend ignores `limit`).
        # An explicit page_size overrides the limit-derived default (used by
        # RemoteClientService.get_all_with_revenue pagination).
        if page_size is None:
            page_size = min(limit, 200) if limit else 200
        return self._get("/api/v1/clients/", params=self._clean_params(
            query=query, limit=limit, page_size=page_size,
            include_inactive=include_inactive, page=page,
        ))

    def get_client(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}")

    def create_client(self, name: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {"name": name, "data": data or {}}
        return self._post("/api/v1/clients/", json_data=body)

    def update_client(self, client_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._put(f"/api/v1/clients/{client_id}", json_data=data)

    def get_client_dashboard(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/dashboard")

    def get_client_trips(self, client_id: int, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/trips",
                         params=self._clean_params(limit=limit, offset=offset))

    def get_client_invoices(self, client_id: int, limit: int = 100) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/invoices",
                         params=self._clean_params(limit=limit))

    def get_client_trip_count(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/trip-count")

    def deactivate_client(self, client_id: int) -> Dict[str, Any]:
        return self._post(f"/api/v1/clients/{client_id}/deactivate")

    def merge_clients(self, from_id: int, to_id: int) -> Dict[str, Any]:
        return self._post("/api/v1/clients/merge",
                          json_data={"from_id": from_id, "to_id": to_id})

    def get_client_contacts(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/contacts")

    def add_client_contact(self, client_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/api/v1/clients/{client_id}/contacts", json_data=data)

    def update_client_contact(self, contact_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._patch(f"/api/v1/clients/contacts/{contact_id}", json_data=data)

    def delete_client_contact(self, contact_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/clients/contacts/{contact_id}")

    def get_client_tags(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/tags")

    def add_client_tag(self, client_id: int, tag: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/clients/{client_id}/tags", json_data={"tag": tag})

    def get_client_payment_summary(self, client_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/payment-summary")

    def get_client_revenue_history(self, client_id: int, months: int = 12) -> Dict[str, Any]:
        return self._get(f"/api/v1/clients/{client_id}/revenue-history",
                         params=self._clean_params(months=months))

    # ── Fleet endpoints ───────────────────────────────────────────────

    def list_trucks(self, page: int = 1, page_size: int = 200) -> Dict[str, Any]:
        """Return a paginated list of trucks.

        ``GET /fleet/trucks`` exposes ``page``/``page_size`` query params
        (``page_size`` is capped at 200 by the backend); sending them
        explicitly keeps the request well-formed and matches how
        ``list_clients`` forwards pagination params.
        """
        return self._get("/api/v1/fleet/trucks", params=self._clean_params(
            page=page, page_size=page_size,
        ))

    def get_truck(self, truck_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/fleet/trucks/{truck_id}")

    def create_truck(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/api/v1/fleet/trucks", json_data=data)

    def update_truck(self, truck_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._put(f"/api/v1/fleet/trucks/{truck_id}", json_data=data)

    def delete_truck(self, truck_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/fleet/trucks/{truck_id}")

    def ingest_gps_ping(self, truck_id: int, latitude: float, longitude: float,
                        speed_kmh: float = 0.0, heading: int = 0,
                        timestamp: str = "", driver_id: Optional[int] = None) -> Dict[str, Any]:
        return self._post("/api/v1/fleet/gps/ingest", json_data={
            "truck_id": truck_id, "latitude": latitude, "longitude": longitude,
            "speed_kmh": speed_kmh, "heading": heading,
            "timestamp": timestamp, "driver_id": driver_id,
        })

    def get_live_position(self, truck_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/fleet/gps/live/{truck_id}")

    def ingest_gps_batch(self, pings: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self._post("/api/v1/fleet/gps/batch", json_data=pings)

    def get_gps_history(self, truck_id: int, limit: int = 100) -> Dict[str, Any]:
        return self._get(f"/api/v1/fleet/gps/history/{truck_id}",
                         params=self._clean_params(limit=limit))

    # ── Driver endpoints ──────────────────────────────────────────────

    def list_drivers(self, limit: int = 500, offset: int = 0) -> Dict[str, Any]:
        return self._get("/api/v1/drivers/",
                         params=self._clean_params(limit=limit, offset=offset))

    def get_driver(self, driver_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/drivers/{driver_id}")

    def create_driver(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("/api/v1/drivers/", json_data=data)

    def update_driver(self, driver_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._put(f"/api/v1/drivers/{driver_id}", json_data=data)

    def delete_driver(self, driver_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/drivers/{driver_id}")

    def assign_driver_to_truck(self, driver_id: int, truck_id: int) -> Dict[str, Any]:
        return self._post(f"/api/v1/drivers/{driver_id}/assign-truck",
                          json_data={"truck_id": truck_id})

    def unassign_driver(self, driver_id: int) -> Dict[str, Any]:
        return self._post(f"/api/v1/drivers/{driver_id}/unassign")

    def get_driver_truck_plate(self, driver_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/drivers/{driver_id}/truck-plate")

    def get_driver_tacho_activity(self, driver_id: int, from_date: str = "",
                                   limit: int = 100) -> Dict[str, Any]:
        return self._get(f"/api/v1/drivers/{driver_id}/tacho-activity",
                         params=self._clean_params(from_date=from_date, limit=limit))

    # ── Route endpoints ───────────────────────────────────────────────

    def list_route_history(self, limit: int = 50) -> Dict[str, Any]:
        return self._get("/api/v1/routes/history",
                         params=self._clean_params(limit=limit))

    def get_route_history(self, route_id: int) -> Dict[str, Any]:
        return self._get(f"/api/v1/routes/history/{route_id}")

    def calculate_route(self, points: List[Any], profile: str = "truck") -> Dict[str, Any]:
        return self._post("/api/v1/routes/calculate", json_data={
            "points": points, "profile": profile,
        })

    def duplicate_route(self, route_id: int) -> Dict[str, Any]:
        return self._post(f"/api/v1/routes/history/{route_id}/duplicate")

    def archive_route(self, route_id: int) -> Dict[str, Any]:
        return self._post(f"/api/v1/routes/history/{route_id}/archive")

    def delete_route_history(self, route_id: int) -> Dict[str, Any]:
        return self._delete(f"/api/v1/routes/history/{route_id}")

    def export_route(self, route_id: int, fmt: str = "json") -> Dict[str, Any]:
        return self._get(f"/api/v1/routes/history/{route_id}/export",
                         params=self._clean_params(fmt=fmt))

    def get_route_statistics(self) -> Dict[str, Any]:
        return self._get("/api/v1/routes/history/statistics")

    # ── Analytics endpoints ───────────────────────────────────────────

    # ── Financial ───────────────────────────────────────────────────

    def get_analytics_financial(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_financial_monthly(self, months: int = 24,
                                         from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/monthly",
                         params=self._clean_params(months=months, from_date=from_date, to_date=to_date))

    def get_analytics_financial_cost_breakdown(self, months: int = 12,
                                                from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/cost-breakdown",
                         params=self._clean_params(months=months, from_date=from_date, to_date=to_date))

    def get_analytics_financial_trip_status(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/trip-status",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_financial_trip_volume(self, months: int = 12,
                                             from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/trip-volume",
                         params=self._clean_params(months=months, from_date=from_date, to_date=to_date))

    def get_analytics_financial_by_country(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/by-country",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_financial_quarterly(self, quarters: int = 8,
                                           from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/quarterly",
                         params=self._clean_params(quarters=quarters, from_date=from_date, to_date=to_date))

    def get_analytics_financial_invoice_aging(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/financial/invoice-aging")

    # ── Client ──────────────────────────────────────────────────────

    def get_analytics_client(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/client",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_client_growth(self, months: int = 12,
                                     from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/client/growth",
                         params=self._clean_params(months=months, from_date=from_date, to_date=to_date))

    def get_analytics_client_retention(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/client/retention")

    def get_analytics_client_concentration(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/client/concentration")

    def get_analytics_revenue_by_client(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/revenue-by-client",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    # ── Fleet ───────────────────────────────────────────────────────

    def get_analytics_fleet(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/fleet",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_fleet_utilization(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/fleet/utilization")

    # ── Route ───────────────────────────────────────────────────────

    def get_analytics_route_profitability(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/route/profitability",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_route_by_country(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/route/by-country")

    def get_analytics_route_profit_vs_distance(self, limit: int = 100) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/route/profit-vs-distance",
                         params=self._clean_params(limit=limit))

    # ── Driver ──────────────────────────────────────────────────────

    def get_analytics_driver(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/driver",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_driver_comparison(self, from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/driver/comparison",
                         params=self._clean_params(from_date=from_date, to_date=to_date))

    def get_analytics_driver_profit_per_km(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/driver/profit-per-km")

    def get_analytics_driver_violations(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/driver/violations")

    def get_analytics_driver_monthly_activity(self, months: int = 12,
                                               from_date: str = "", to_date: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/analytics/driver/monthly-activity",
                         params=self._clean_params(months=months, from_date=from_date, to_date=to_date))

    # ── Document ─────────────────────────────────────────────────────

    def get_analytics_document(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/document")

    def get_analytics_document_upload_trend(self, months: int = 12) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/document/upload-trend",
                         params=self._clean_params(months=months))

    # ── Maintenance ──────────────────────────────────────────────────

    def get_analytics_maintenance_alerts(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/maintenance/alerts")

    def get_analytics_overview(self) -> Dict[str, Any]:
        return self._get("/api/v1/analytics/overview")

    def invalidate_analytics_cache(self) -> Dict[str, Any]:
        return self._post("/api/v1/analytics/invalidate")

    # ── Maintenance endpoints ─────────────────────────────────────────

    def get_maintenance_summary(self) -> Dict[str, Any]:
        return self._get("/api/v1/maintenance/summary")

    def get_maintenance_cost_monthly(self, date_from: str = "", since: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/maintenance/cost-monthly",
                         params=self._clean_params(date_from=date_from, since=since))

    def get_maintenance_cost_by_truck_monthly(self, date_from: str = "", since: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/maintenance/cost-by-truck-monthly",
                         params=self._clean_params(date_from=date_from, since=since))

    def get_maintenance_truck_summary(self, date_from: str = "", since: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/maintenance/truck-summary",
                         params=self._clean_params(date_from=date_from, since=since))

    def get_maintenance_top_categories(self, date_from: str = "", since: str = "") -> Dict[str, Any]:
        return self._get("/api/v1/maintenance/top-categories",
                         params=self._clean_params(date_from=date_from, since=since))

    # ── Alerts endpoints ──────────────────────────────────────────────

    def list_alerts(self, limit: int = 50) -> Dict[str, Any]:
        return self._get("/api/v1/alerts/", params=self._clean_params(limit=limit))

    def get_alert_count(self) -> Dict[str, Any]:
        return self._get("/api/v1/alerts/count")

    def resolve_alert(self, alert_id: str) -> Dict[str, Any]:
        return self._post(f"/api/v1/alerts/{alert_id}/resolve")

    # ── Settings endpoints ────────────────────────────────────────────

    def get_company_config(self) -> Dict[str, Any]:
        return self._get("/api/v1/settings/company")

    def save_company_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._put("/api/v1/settings/company", json_data=data)

    def get_setting(self, key: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/settings/{key}")

    def save_setting(self, key: str, value: str) -> Dict[str, Any]:
        return self._put(f"/api/v1/settings/{key}", json_data={"value": value})

    def get_settings_bulk(self, keys) -> Dict[str, Any]:
        """Fetch multiple settings in one request (Phase D — settings sync).

        ``keys`` is an iterable of setting keys.  Returns the server response
        ``{"values": {key: value_or_None}}`` (missing keys are ``None``, not
        a 404 — a multi-key pull must not need N round-trips).
        """
        return self._get(
            "/api/v1/settings/bulk",
            params={"keys": ",".join(keys)},
        )

    def reconcile_sequences(self, entity: str, year: int, value: int) -> Dict[str, Any]:
        """Reconcile a document sequence counter (Phase D).

        Tells the server to bump its counter for ``entity`` (``"invoice"`` or
        ``"cmr"``) to ``max(existing, value)`` — a lower value is a no-op, so
        a stale desktop can never decrease the shared counter.
        """
        return self._post(
            "/api/v1/sync/sequences",
            json_data={"entity": entity, "year": year, "value": value},
        )

    # ── Support endpoints ─────────────────────────────────────────────

    def report_issue(
        self, subject: str, description: str,
        severity: str = "medium",
        screenshot_bytes: bytes | None = None,
        screenshot_filename: str = "screenshot.png",
    ) -> Dict[str, Any]:
        """Send a support ticket via POST to the backend proxy.

        Args:
            subject: Short summary of the issue.
            description: Detailed description.
            severity: One of ``"low"``, ``"medium"``, ``"high"``, ``"critical"``.
            screenshot_bytes: Optional raw PNG/JPEG bytes to attach.
            screenshot_filename: Filename for the attached screenshot
                                 (default ``screenshot.png``).

        Returns:
            Server response as a dict (e.g. ``{"id": ..., "status": ...}``).
        """
        body: Dict[str, Any] = {
            "subject": subject,
            "description": description,
            "severity": severity,
        }
        if screenshot_bytes is not None:
            import base64
            body["screenshot"] = base64.b64encode(screenshot_bytes).decode("ascii")
            body["screenshot_filename"] = screenshot_filename
        return self._post("/api/v1/support/messages", json_data=body)

    # ── Tacho endpoints ───────────────────────────────────────────────

    def get_tacho_import_history(self, limit: int = 50) -> Dict[str, Any]:
        return self._get("/api/v1/tacho/import-history",
                         params=self._clean_params(page_size=limit))

    def get_tacho_status(self) -> Dict[str, Any]:
        return self._get("/api/v1/tacho/status")

    # ── Invoice endpoints ─────────────────────────────────────────────

    def generate_invoice(self, trip_data: Dict[str, Any], mode: str = "client") -> bytes:
        """Generate an invoice PDF via ``POST /api/v1/invoices/generate``.

        Returns PDF bytes (a :class:`PdfWithRecord`).  When the server
        assigns or confirms the invoice number it is surfaced on the returned
        object as ``result.record`` — e.g. ``{"invoice_number":
        "INV-2026-0042", "id": 12}``.

        The request body is the flat schema payload (``trip_id``, ``mode``,
        optional ``invoice_number``/``client_name``/``total_price_eur``/…)
        expected by ``InvoiceGenerateRequest``; the ``trip_data`` dict is
        translated so the trip row's ``id`` becomes ``trip_id``.
        """
        payload: Dict[str, Any] = {
            "trip_id": trip_data.get("trip_id") or trip_data.get("id") or 0,
            "mode": mode,
        }
        for field in ("invoice_number", "client_name", "total_price_eur",
                      "client_id", "language", "additional_notes", "created_at"):
            value = trip_data.get(field)
            if value is not None:
                payload[field] = value
        resp = self._request_with_retry(
            "POST", f"{self._base_url}/api/v1/invoices/generate", json=payload,
        )
        resp.raise_for_status()
        record: Dict[str, Any] = {}
        try:
            headers = getattr(resp, "headers", None) or {}
            num = headers.get("X-Invoice-Number")
            if num:
                record["invoice_number"] = str(num)
            inv_id = headers.get("X-Invoice-Id")
            if inv_id:
                try:
                    record["id"] = int(str(inv_id))
                except (TypeError, ValueError):
                    record["id"] = str(inv_id)
        except Exception:
            pass
        return PdfWithRecord(resp.content, record=record)

    def send_invoice_email(self, invoice_id: int, recipient: str,
                           trip_data: Optional[Dict[str, Any]] = None,
                           mode: str = "client") -> Dict[str, Any]:
        return self._post(f"/api/v1/invoices/{invoice_id}/send", json_data={
            "recipient": recipient,
            "trip_data": trip_data or {},
            "mode": mode,
        })

    # ── CMR endpoints ─────────────────────────────────────────────────

    def generate_cmr(self, trip_data: Dict[str, Any]) -> bytes:
        return self._post_binary("/api/v1/cmr/generate",
                                 json_data={"trip_data": trip_data})

    # ── Receipt endpoints ─────────────────────────────────────────────

    def generate_receipt(self, receipt_data: Dict[str, Any]) -> bytes:
        return self._post_binary("/api/v1/receipts/generate",
                                 json_data={"receipt_data": receipt_data})

    # ── Admin endpoints ───────────────────────────────────────────────

    def get_admin_diagnostics(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/diagnostics")

    def get_admin_db_tables(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/db/tables")

    def get_admin_db_table_schema(self, table_name: str) -> Dict[str, Any]:
        return self._get(f"/api/v1/admin/db/table/{table_name}/schema")

    def get_admin_db_table_data(
        self, table_name: str, page: int = 0, page_size: int = 100,
    ) -> Dict[str, Any]:
        return self._get(f"/api/v1/admin/db/table/{table_name}", params={
            "page": page, "page_size": page_size,
        })

    def execute_admin_query(self, query: str) -> Dict[str, Any]:
        return self._post("/api/v1/admin/db/query", json_data={"query": query})

    def get_admin_document_stats(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/documents/stats")

    def get_admin_document_orphans(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/documents/orphans")

    def get_admin_system_info(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/system/info")

    def get_admin_system_env(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/system/env")

    def get_admin_logs_tail(self, lines: int = 100) -> Dict[str, Any]:
        return self._get("/api/v1/admin/logs/tail", params={"lines": lines})

    def clear_admin_cache(self) -> Dict[str, Any]:
        return self._post("/api/v1/admin/cache/clear")

    def get_admin_detailed_health(self) -> Dict[str, Any]:
        return self._get("/api/v1/admin/health/detailed")

    # ── Health ────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        return self._get("/api/v1/health")

    # ── User management endpoints ────────────────────────────────────────

    def list_users(self, company_id: int | None = None) -> Dict[str, Any]:
        """List users in the current company."""
        params: dict = {}
        if company_id is not None:
            params["company_id"] = company_id
        return self._get("/api/v1/users/", params=params)

    def create_user(self, email: str, password: str, role: str,
                    display_name: str = "", driver_id: int | None = None) -> Dict[str, Any]:
        """Create a new user (manager-only)."""
        body: dict = {
            "email": email,
            "password": password,
            "role": role,
            "display_name": display_name,
        }
        return self._post("/api/v1/users/", json_data=body)

    def update_user(self, user_id: int, **fields: Any) -> Dict[str, Any]:
        """Update a user (manager-only)."""
        return self._put(f"/api/v1/users/{user_id}", json_data=fields)

    def deactivate_user(self, user_id: int) -> Dict[str, Any]:
        """Deactivate a user (manager-only)."""
        return self._delete(f"/api/v1/users/{user_id}")

    def close(self) -> None:
        self._client.close()


class DualModeDocumentService:
    def __init__(self, db=None, api_client: Optional[ApiClient] = None):
        self._db = db
        self._api = api_client or ApiClient()
        self._local: Any = None

    def _get_local(self) -> Any:
        if self._local is None and self._db is not None:
            from services.document_service import DocumentService
            self._local = DocumentService(self._db)
        return self._local

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        if self._api.is_online():
            try:
                return self._api.get_document(doc_id)
            except Exception:
                pass
        local = self._get_local()
        return local.get_by_id(doc_id) if local else None

    def list_documents(self, **kwargs: Any) -> Dict[str, Any]:
        if self._api.is_online():
            try:
                return self._api.list_documents(**kwargs)
            except Exception:
                pass
        local = self._get_local()
        if local:
            return local.advanced_search(**kwargs)
        return {"items": [], "total": 0}

    def read_document_info(self, doc_id: int) -> Dict[str, Any]:
        if self._api.is_online():
            try:
                return self._api.read_document_info(doc_id)
            except Exception:
                pass
        local = self._get_local()
        if local:
            doc = local.get_by_id(doc_id)
            if doc:
                return {
                    "document": doc,
                    "ocr_text": doc.get("ocr_text", ""),
                    "extracted_fields": doc.get("extracted_data_json", {}),
                    "linked_entities": local.get_links(doc_id),
                    "versions": local.get_versions(doc_id),
                    "tags": doc.get("tags", []),
                    "expiry": doc.get("expiry_date", ""),
                }
        return {}

    def get_categories(self) -> List[Dict[str, Any]]:
        if self._api.is_online():
            try:
                return self._api.get_document_categories()
            except Exception:
                pass
        local = self._get_local()
        if local:
            return local.get_categories()
        return []

    def get_links(self, doc_id: int) -> List[Dict[str, Any]]:
        if self._api.is_online():
            try:
                return self._api.get_document_links(doc_id)
            except Exception:
                pass
        local = self._get_local()
        if local:
            return local.get_links(doc_id)
        return []

    def get_versions(self, doc_id: int) -> List[Dict[str, Any]]:
        if self._api.is_online():
            try:
                return self._api.get_document_versions(doc_id)
            except Exception:
                pass
        local = self._get_local()
        if local:
            return local.get_versions(doc_id)
        return []

    def health(self) -> Dict[str, Any]:
        return self._api.health_check()
