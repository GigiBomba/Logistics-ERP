"""Comprehensive unit tests for SecurityHeadersMiddleware.

Tests cover:
- All security headers are present on responses
- Header values are correct/valid
- Development mode (is_production=False) has relaxed CORS
- Production mode (is_production=True) has strict CSP
- CSP connect-src construction includes configured origins
- Permissions-Policy header value correct
- HSTS max-age and includeSubDomains
- Middleware does not interfere with normal response operation
- Edge cases: missing headers don't cause crashes
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.middleware.security_headers_middleware import (
    API_DOMAIN,
    SecurityHeadersMiddleware,
)


# ── Constants ──────────────────────────────────────────────────────────

EXPECTED_HSTS = "max-age=31536000; includeSubDomains"
EXPECTED_XCTO = "nosniff"
EXPECTED_XFO = "DENY"
EXPECTED_REFERRER = "strict-origin-when-cross-origin"
EXPECTED_PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(self), "
    "interest-cohort=()"
)

PRODUCTION_CSP_CONNECT_SRC = f"'self' {API_DOMAIN}"
DEV_CSP_CONNECT_SRC = (
    f"'self' {API_DOMAIN} http://localhost:* http://127.0.0.1:*"
)
PRODUCTION_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https://*.tile.openstreetmap.org data:; "
    "font-src 'self'; "
    f"connect-src {PRODUCTION_CSP_CONNECT_SRC}; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)
DEV_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' https://*.tile.openstreetmap.org data:; "
    "font-src 'self'; "
    f"connect-src {DEV_CSP_CONNECT_SRC}; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)


# ── Helpers ────────────────────────────────────────────────────────────


def _build_app(
    is_production: bool = True,
    cors_origins: Sequence[str] | None = None,
) -> FastAPI:
    """Create a FastAPI app with SecurityHeadersMiddleware attached.

    Parameters
    ----------
    is_production :
        Passed through to the middleware constructor.
    cors_origins :
        Passed through to the middleware constructor as the explicit list
        of CORS origins for the CSP ``connect-src`` directive.
    """
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/echo")
    async def echo(payload: dict):
        return {"received": payload}

    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=is_production,
        cors_origins=cors_origins,
    )
    return app


# ═════════════════════════════════════════════════════════════════════
# SecurityHeadersMiddleware
# ═════════════════════════════════════════════════════════════════════


class TestAllSecurityHeadersPresent:
    """Every response must carry the full set of security headers."""

    REQUIRED_HEADERS = {
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "content-security-policy",
        "permissions-policy",
    }

    def test_production_all_headers_present(self):
        """Production mode includes all security headers plus cross-origin policies."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        present = {k.lower() for k in resp.headers}
        missing = self.REQUIRED_HEADERS - present
        assert not missing, f"Missing security headers: {missing}"

        # Production also sets cross-origin policies
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    def test_dev_all_headers_present(self):
        """Development mode includes all security headers."""
        app = _build_app(is_production=False)
        client = TestClient(app)
        resp = client.get("/")

        present = {k.lower() for k in resp.headers}
        missing = self.REQUIRED_HEADERS - present
        assert not missing, f"Missing security headers: {missing}"

    def test_non_root_response_gets_headers(self):
        """Security headers are applied to non-root endpoints as well."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/api/v1/health")

        assert resp.headers.get("strict-transport-security") is not None
        assert resp.headers.get("content-security-policy") is not None
        assert resp.headers.get("x-frame-options") is not None
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_post_response_gets_headers(self):
        """Security headers are applied to POST responses too."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.post("/echo", json={"msg": "hello"})

        assert resp.headers.get("strict-transport-security") is not None
        assert resp.headers.get("content-security-policy") is not None
        assert resp.status_code == 200
        assert resp.json() == {"received": {"msg": "hello"}}


class TestSecurityHeaderValues:
    """Each security header must carry the correct value."""

    def test_hsts_header_value(self):
        """Strict-Transport-Security has max-age and includeSubDomains."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["Strict-Transport-Security"] == EXPECTED_HSTS

    def test_x_content_type_options_value(self):
        """X-Content-Type-Options is 'nosniff'."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["X-Content-Type-Options"] == EXPECTED_XCTO

    def test_x_frame_options_value(self):
        """X-Frame-Options is 'DENY'."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["X-Frame-Options"] == EXPECTED_XFO

    def test_referrer_policy_value(self):
        """Referrer-Policy is 'strict-origin-when-cross-origin'."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["Referrer-Policy"] == EXPECTED_REFERRER


class TestContentSecurityPolicy:
    """Content-Security-Policy header is correctly constructed."""

    def test_production_csp_default(self):
        """Production CSP uses strict defaults with self-only connect-src."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["Content-Security-Policy"] == PRODUCTION_CSP

    def test_dev_csp_includes_localhost(self):
        """Development CSP adds localhost wildcards to connect-src."""
        app = _build_app(is_production=False)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["Content-Security-Policy"] == DEV_CSP

    def test_csp_connect_src_includes_cors_origins(self):
        """CSP connect-src includes user-configured CORS origins."""
        origins = ["https://app.example.com", "https://admin.example.com"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "https://app.example.com" in csp, (
            "connect-src should include https://app.example.com"
        )
        assert "https://admin.example.com" in csp, (
            "connect-src should include https://admin.example.com"
        )

    def test_csp_connect_src_deduplicates_origins(self):
        """Duplicate origins in cors_origins are not added twice."""
        origins = ["https://api.operionerp.xyz", "https://api.operionerp.xyz"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        # 'self' + API_DOMAIN — should appear exactly once each
        assert csp.count(API_DOMAIN) == 1, (
            f"{API_DOMAIN} must not appear more than once in CSP"
        )

    def test_csp_connect_src_strips_whitespace_from_origins(self):
        """Leading/trailing whitespace on origins is stripped."""
        origins = ["  https://app.example.com  ", "\thttps://admin.net\t"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "https://app.example.com" in csp
        assert "https://admin.net" in csp

    def test_csp_connect_src_skips_empty_origins(self):
        """Empty strings in cors_origins are silently skipped."""
        origins = ["", "  ", "https://valid.example.com"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "https://valid.example.com" in csp

    def test_csp_connect_src_no_origins_provided(self):
        """When cors_origins is None, connect-src has only self and API_DOMAIN."""
        app = _build_app(is_production=True, cors_origins=None)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        expected = PRODUCTION_CSP
        assert csp == expected

    def test_csp_connect_src_empty_origins_list(self):
        """When cors_origins is an empty list, connect-src has only defaults."""
        app = _build_app(is_production=True, cors_origins=[])
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        expected = PRODUCTION_CSP
        assert csp == expected

    def test_csp_has_all_directives(self):
        """CSP contains all expected directives."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        directives = ["default-src", "script-src", "style-src", "img-src",
                      "font-src", "connect-src", "frame-ancestors",
                      "base-uri", "form-action"]
        for directive in directives:
            assert directive in csp, f"CSP missing directive '{directive}'"

    def test_csp_img_src_includes_tile_server(self):
        """img-src includes OpenStreetMap tile server and data: URIs."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "https://*.tile.openstreetmap.org" in csp
        assert "data:" in csp

    def test_csp_style_src_unsafe_inline(self):
        """style-src includes 'unsafe-inline'."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "'unsafe-inline'" in csp

    def test_csp_frame_ancestors_none(self):
        """frame-ancestors is 'none' to prevent framing."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp


class TestPermissionsPolicy:
    """Permissions-Policy header must be correctly formatted."""

    def test_permissions_policy_value(self):
        """Permissions-Policy has correct value."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers["Permissions-Policy"] == EXPECTED_PERMISSIONS_POLICY

    def test_permissions_policy_disables_camera(self):
        """Camera is disabled."""
        app = _build_app()
        client = TestClient(app)
        policy = client.get("/").headers["Permissions-Policy"]
        assert "camera=()" in policy

    def test_permissions_policy_disables_microphone(self):
        """Microphone is disabled."""
        app = _build_app()
        client = TestClient(app)
        policy = client.get("/").headers["Permissions-Policy"]
        assert "microphone=()" in policy

    def test_permissions_policy_geolocation_self(self):
        """Geolocation is allowed for self only."""
        app = _build_app()
        client = TestClient(app)
        policy = client.get("/").headers["Permissions-Policy"]
        assert "geolocation=(self)" in policy

    def test_permissions_policy_disables_interest_cohort(self):
        """interest-cohort (FLoC) is disabled."""
        app = _build_app()
        client = TestClient(app)
        policy = client.get("/").headers["Permissions-Policy"]
        assert "interest-cohort=()" in policy


class TestHSTS:
    """Strict-Transport-Security header details."""

    def test_hsts_max_age_one_year(self):
        """HSTS max-age is 31536000 seconds (1 year)."""
        app = _build_app()
        client = TestClient(app)
        hsts = client.get("/").headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts

    def test_hsts_include_subdomains(self):
        """HSTS includes includeSubDomains directive."""
        app = _build_app()
        client = TestClient(app)
        hsts = client.get("/").headers["Strict-Transport-Security"]
        assert "includeSubDomains" in hsts

    def test_hsts_semicolon_separated(self):
        """HSTS directives are separated by semicolons."""
        app = _build_app()
        client = TestClient(app)
        hsts = client.get("/").headers["Strict-Transport-Security"]
        parts = [p.strip() for p in hsts.split(";")]
        assert "max-age=31536000" in parts
        assert "includeSubDomains" in parts
        assert len(parts) == 2


class TestProductionVsDevelopment:
    """Differences between production and development modes."""

    def test_production_has_cross_origin_policies(self):
        """Production mode sets strict cross-origin policies."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"
        assert resp.headers.get("Cross-Origin-Opener-Policy") == "same-origin"

    def test_dev_missing_cross_origin_policies(self):
        """Development mode does NOT set cross-origin policies."""
        app = _build_app(is_production=False)
        client = TestClient(app)
        resp = client.get("/")
        assert "Cross-Origin-Resource-Policy" not in resp.headers
        assert "Cross-Origin-Opener-Policy" not in resp.headers

    def test_production_connect_src_no_localhost(self):
        """Production CSP does not include localhost wildcards."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        assert "http://localhost:*" not in csp
        assert "http://127.0.0.1:*" not in csp

    def test_dev_connect_src_includes_localhost(self):
        """Development CSP includes localhost wildcards."""
        app = _build_app(is_production=False)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        assert "http://localhost:*" in csp
        assert "http://127.0.0.1:*" in csp

    def test_production_isolation_does_not_leak_into_dev(self):
        """Multiple apps in the same test keep prod and dev CSP separate."""
        prod_app = _build_app(is_production=True)
        dev_app = _build_app(is_production=False)
        prod_client = TestClient(prod_app)
        dev_client = TestClient(dev_app)

        prod_csp = prod_client.get("/").headers["Content-Security-Policy"]
        dev_csp = dev_client.get("/").headers["Content-Security-Policy"]

        assert "http://localhost:*" not in prod_csp
        assert "http://localhost:*" in dev_csp


class TestCorsOrigins:
    """CSP connect-src is correctly built from cors_origins."""

    def test_single_origin_added(self):
        """A single custom origin appears in connect-src."""
        app = _build_app(is_production=True, cors_origins=["https://custom.app"])
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        assert "https://custom.app" in csp

    def test_multiple_origins_added(self):
        """Multiple custom origins all appear in connect-src."""
        origins = ["https://a.example.com", "https://b.example.com",
                   "https://c.example.com"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        for origin in origins:
            assert origin in csp, f"Missing origin {origin} in connect-src"

    def test_origin_overlapping_with_api_domain_is_deduplicated(self):
        """If cors_origins includes the API_DOMAIN, it appears only once."""
        origins = [API_DOMAIN]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        assert csp.count(API_DOMAIN) == 1

    def test_origin_matching_self_is_not_duplicated_in_connect_src(self):
        """If cors_origins contains 'self', connect-src does not duplicate it."""
        origins = ["'self'"]
        app = _build_app(is_production=True, cors_origins=origins)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        # Extract the connect-src directive value
        connect_src_part = ""
        for part in csp.split(";"):
            if part.strip().startswith("connect-src"):
                connect_src_part = part.strip()
                break
        # The 'self' should appear exactly once in connect-src
        assert connect_src_part.count("'self'") == 1, (
            f"'self' should appear exactly once in connect-src, "
            f"got: {connect_src_part}"
        )

    def test_dev_mode_origins_preserved_with_localhost(self):
        """In dev mode, custom origins are preserved alongside localhost wildcards."""
        app = _build_app(
            is_production=False,
            cors_origins=["https://dev-tool.local"],
        )
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]

        assert "https://dev-tool.local" in csp
        assert "http://localhost:*" in csp
        assert "http://127.0.0.1:*" in csp


class TestNormalResponseOperation:
    """Middleware does not interfere with normal response operation."""

    def test_status_code_preserved(self):
        """Response status code is unchanged by the middleware."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_response_body_preserved(self):
        """Response body content is unchanged."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.json() == {"ok": True}

    def test_response_body_for_health_endpoint(self):
        """Health endpoint still returns its expected payload."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.json() == {"status": "healthy"}

    def test_post_body_preserved(self):
        """POST request payload roundtrips correctly."""
        app = _build_app()
        client = TestClient(app)
        payload = {"hello": "world", "number": 42}
        resp = client.post("/echo", json=payload)
        assert resp.json() == {"received": payload}

    def test_multiple_sequential_requests(self):
        """Multiple sequential requests all get security headers."""
        app = _build_app()
        client = TestClient(app)

        for _ in range(20):
            resp = client.get("/")
            assert resp.headers.get("Content-Security-Policy") is not None
            assert resp.headers.get("X-Frame-Options") is not None
            assert resp.status_code == 200


class TestEdgeCases:
    """Edge cases that should not cause crashes or misbehaviour."""

    def test_no_cors_origins_default(self):
        """Middleware works with default parameters (no cors_origins)."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["Content-Security-Policy"] == PRODUCTION_CSP

    def test_cors_origins_none(self):
        """Middleware works when cors_origins is explicitly None."""
        app = _build_app(is_production=True, cors_origins=None)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_cors_origins_empty_list(self):
        """Middleware works with empty cors_origins list."""
        app = _build_app(is_production=True, cors_origins=[])
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200

    def test_cors_origins_with_whitespace_only(self):
        """Middleware handles cors_origins containing only whitespace strings."""
        app = _build_app(is_production=True, cors_origins=["   ", "\t\n"])
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        # No extra origins beyond defaults should be present
        assert resp.headers["Content-Security-Policy"] == PRODUCTION_CSP

    def test_cors_origins_with_none_values_raises(self):
        """Middleware raises AttributeError when cors_origins contains None
        (the type annotation is ``Sequence[str]``, so this is a programmer
        error and should fail fast at request time)."""
        app = _build_app(is_production=True, cors_origins=[None])  # type: ignore[list-item]
        client = TestClient(app)
        with pytest.raises(AttributeError, match="strip"):
            client.get("/")

    def test_middleware_default_is_production(self):
        """Default constructor sets is_production=True."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        assert resp.headers.get("Cross-Origin-Resource-Policy") == "same-origin"

    def test_api_domain_constant_in_connect_src(self):
        """API_DOMAIN constant is present in the connect-src."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        csp = client.get("/").headers["Content-Security-Policy"]
        assert API_DOMAIN in csp
        # Remove the scheme+slashes and check the domain part
        assert "api.operionerp.xyz" in csp

    def test_header_names_are_case_insensitive(self):
        """Headers can be looked up case-insensitively (HTTP standard)."""
        app = _build_app()
        client = TestClient(app)
        resp = client.get("/")
        # These should all work regardless of casing
        assert resp.headers.get("STRICT-TRANSPORT-SECURITY") is not None
        assert resp.headers.get("content-security-policy") is not None
        assert resp.headers.get("X-FRAME-OPTIONS") is not None

    def test_response_has_no_extra_unexpected_headers(self):
        """Only expected security headers are added (no accidental extras)."""
        app = _build_app(is_production=True)
        client = TestClient(app)
        resp = client.get("/")

        # Headers that FastAPI/Starlette/TestClient set by default
        known_headers = {
            "content-length",
            "content-type",
            "date",
            "server",
        }
        # Security headers the middleware adds
        security_headers = {
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy",
            "content-security-policy",
            "permissions-policy",
            "cross-origin-resource-policy",
            "cross-origin-opener-policy",
        }
        all_known = known_headers | security_headers
        for header in resp.headers:
            assert header.lower() in all_known, (
                f"Unexpected header '{header}' in response"
            )
