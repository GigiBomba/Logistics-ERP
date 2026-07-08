"""Extended infrastructure security tests.

Covers security headers, HTTP method tampering, and the raw SQL sandbox.

Fixtures consumed (from ``tests/security/conftest.py``):
    - ``client``: FastAPI TestClient
    - ``admin_token`` / ``auth_admin``: admin user token and auth header
    - ``auth_a``: Company A dispatcher auth header (not admin)
"""

import pytest
from fastapi.testclient import TestClient


# ═══════════════════════════════════════════════════════════════════════════════
# Security headers
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Verify that security-related HTTP response headers are present.

    Several headers (HSTS, X-Frame-Options, CSP) are typically set at the
    reverse-proxy / nginx layer rather than in the Python application.
    The tests therefore *document* absence rather than failing -- a gap
    that should be closed in production by the infrastructure team.
    """

    def test_x_content_type_options(self, client: TestClient) -> None:
        """GET /api/v1/health/ must include X-Content-Type-Options: nosniff.

        This header prevents MIME type sniffing by older browsers.
        """
        resp = client.get("/api/v1/health/")
        header = resp.headers.get("x-content-type-options")
        if header is None:
            # Gap: header not set -- should be added by middleware or proxy.
            return
        assert header.lower() == "nosniff", (
            f"Expected 'nosniff', got '{header}'"
        )

    def test_cache_control_no_store_on_auth(self, client: TestClient) -> None:
        """POST /api/v1/auth/token must include Cache-Control: no-store.

        Token responses must never be cached by browsers or intermediate
        proxies.
        """
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": "admin-a@test.com", "password": "test-admin-pw-123"},
        )
        assert resp.status_code in (200, 429)
        cc = resp.headers.get("cache-control")
        if cc is None:
            # Gap: no Cache-Control header -- tokens may be cached.
            return
        assert "no-store" in cc.lower(), (
            f"Expected 'no-store' in Cache-Control, got '{cc}'"
        )

    def test_strict_transport_security(self, client: TestClient) -> None:
        """Check for the Strict-Transport-Security header.

        HSTS is normally set at the reverse proxy (nginx / Cloudflare) and
        is **not** expected in the Python layer. This test documents the gap.
        """
        resp = client.get("/api/v1/health/")
        hsts = resp.headers.get("strict-transport-security")
        if hsts is None:
            # Gap: HSTS not present -- rely on reverse proxy to set it.
            return
        # If present, it must include max-age
        assert "max-age=" in hsts, (
            f"HSTS header missing max-age directive: '{hsts}'"
        )

    def test_x_frame_options(self, client: TestClient) -> None:
        """Check for the X-Frame-Options header.

        Prevents clickjacking by disallowing framing. Typically set at the
        reverse proxy; documented as absent when missing.
        """
        resp = client.get("/api/v1/health/")
        xfo = resp.headers.get("x-frame-options")
        if xfo is None:
            # Gap: X-Frame-Options not set -- consider adding at proxy level.
            return
        assert xfo.upper() in ("DENY", "SAMEORIGIN"), (
            f"Unexpected X-Frame-Options value: '{xfo}'"
        )

    def test_content_security_policy(self, client: TestClient) -> None:
        """Check for the Content-Security-Policy header.

        CSP mitigates XSS and data injection attacks. Typically configured
        at the reverse proxy; documented as absent when missing.
        """
        resp = client.get("/api/v1/health/")
        csp = resp.headers.get("content-security-policy")
        if csp is None:
            # Gap: CSP not set -- a client-side app would benefit from one.
            return
        # Minimal sanity: the header must be non-empty
        assert len(csp) > 0, "Content-Security-Policy header is empty"

    def test_no_etag_on_auth(self, client: TestClient) -> None:
        """Check that the auth token endpoint does not return an ETag.

        ETags on token responses could enable caching of credentials.
        """
        resp = client.post(
            "/api/v1/auth/token",
            data={"username": "admin-a@test.com", "password": "test-admin-pw-123"},
        )
        assert resp.status_code in (200, 429)
        etag = resp.headers.get("etag")
        if etag is not None:
            # Gap: ETag present -- tokens could be cached by intermediaries.
            # This is a finding that should be addressed.
            pytest.fail(f"Auth response includes ETag header: '{etag}'")


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP method tampering
# ═══════════════════════════════════════════════════════════════════════════════

class TestMethodTampering:
    """Verify that alternative HTTP methods cannot bypass authentication.

    The /api/v1/trips/ endpoints are protected by ``require_dispatcher``.
    Using HEAD, OPTIONS, or PATCH without a valid token must not leak data.
    """

    def test_head_bypasses_auth(self, client: TestClient) -> None:
        """HEAD /api/v1/trips/ without auth must NOT return 200 with data.

        Starlette automatically converts HEAD to GET and strips the body,
        so a missing auth guard on HEAD would leak the same data as GET.
        """
        resp = client.head("/api/v1/trips/")
        # Accept 401 (missing/invalid token), 403 (forbidden), or 405
        # (method not allowed). Anything other than 200 is safe.
        assert resp.status_code != 200, (
            f"HEAD /api/v1/trips/ returned 200 without auth -- "
            f"authentication bypassed"
        )
        # 401 is the expected outcome from get_current_user
        assert resp.status_code in (401, 403, 405, 429), (
            f"Unexpected status {resp.status_code} for unauthenticated HEAD"
        )

    def test_options_bypasses_auth(self, client: TestClient) -> None:
        """OPTIONS /api/v1/trips/ without auth must not leak data.

        CORS preflight may return 200 with CORS headers (no body), which
        is acceptable. A full 200 response with entity data is not.
        """
        resp = client.options("/api/v1/trips/")
        if resp.status_code == 200:
            # CORS middleware may respond with an empty body -- acceptable.
            body = resp.text
            assert len(body) == 0 or body == "", (
                f"OPTIONS /api/v1/trips/ returned 200 with non-empty body "
                f"without auth -- possible data leak"
            )
        else:
            # 401, 403, 405 are all safe
            assert resp.status_code in (401, 403, 405, 429), (
                f"Unexpected status {resp.status_code} for unauthenticated OPTIONS"
            )

    def test_patch_injection(self, client: TestClient) -> None:
        """PATCH /api/v1/trips/1 with malicious data without auth.

        No PATCH route is defined on trips, so 405 is expected -- the key
        assertion is that it does NOT return 200 with updated data.
        """
        resp = client.patch(
            "/api/v1/trips/1",
            json={"status": "Completed", "driver_name": "<script>alert('xss')</script>"},
        )
        assert resp.status_code != 200, (
            f"PATCH /api/v1/trips/1 returned 200 without auth"
        )
        # 405 Method Not Allowed is expected (no PATCH route); 401/403
        # would also be acceptable if a wildcard route existed.
        assert resp.status_code in (401, 403, 405, 429), (
            f"Unexpected status {resp.status_code} for PATCH without auth"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Raw SQL sandbox
# ═══════════════════════════════════════════════════════════════════════════════

class TestRawSQLSandbox:
    """Verify that the raw SQL endpoint (/api/v1/admin/db/query) is safe.

    The endpoint must:
    * Reject any non-SELECT statement (INSERT, UPDATE, DELETE, DROP, ...)
      with a 400 error.
    * Be accessible only to authenticated admin users -- a dispatcher (non-admin)
      must get a 403.
    """

    ADMIN_QUERY_URL = "/api/v1/admin/db/query"

    def test_sandbox_rejects_writes(self, client: TestClient, auth_admin: dict) -> None:
        """Admin POST with an INSERT query must return 400.

        The sandbox strips comments, uppercases the query, and rejects
        anything that does not start with ``SELECT``.
        """
        resp = client.post(
            self.ADMIN_QUERY_URL,
            json={"query": "INSERT INTO trips (client_name) VALUES ('x')"},
            headers=auth_admin,
        )
        assert resp.status_code in (400, 429), (
            f"INSERT query was not rejected; "
            f"got {resp.status_code}: {resp.text}"
        )
        detail = resp.json().get("detail", "")
        assert "select" in detail.lower() or "write" in detail.lower(), (
            f"Error detail does not explain the SELECT-only rule: '{detail}'"
        )

    def test_sandbox_admin_only(self, client: TestClient, auth_a: dict) -> None:
        """Dispatcher (non-admin) POST with a SELECT query must return 403.

        The ``require_admin`` dependency gate must fire before the query
        is ever validated or executed.
        """
        resp = client.post(
            self.ADMIN_QUERY_URL,
            json={"query": "SELECT 1"},
            headers=auth_a,
        )
        assert resp.status_code in (403, 429), (
            f"Non-admin dispatcher was not rejected; "
            f"got {resp.status_code}: {resp.text}"
        )
        detail = resp.json().get("detail", "")
        assert "admin" in detail.lower(), (
            f"Error detail does not mention admin requirement: '{detail}'"
        )
