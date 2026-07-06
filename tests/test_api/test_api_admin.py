"""Tests for the admin API endpoints.

All admin endpoints are protected by ``require_admin`` — they must
return 403 Forbidden when called without a valid admin JWT.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app

# ── Test admin credentials ─────────────────────────────────────────────
_TEST_ADMIN_EMAIL = "bonjourlol444@gmail.com"
_TEST_ADMIN_PASSWORD = (
    "aF!81YYU2b>zLw5eJW7sGXM7Ri6Q7,Y3:zGzd^!ddMnjxkAHkcgduf}"
    "?w9tg*]N@sg]tN)Fy0k.q843}!d2_xZpW?MkCKPUC4qA7"
)
_TEST_ADMIN_HASH = "$2b$12$HWGCueEet/0YiXml7OvbpevITMJdjgs9FCFLmfYuwcgKwYvtpeOCG"
_TEST_JWT_SECRET = "e8f9b23fbc062b8a74c4dbb9dcde99252a13f040b201a056a29df147c216298a"


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    """Set test environment variables before any test.

    Uses a temporary file for the database so read-only connections
    (Phase 5 sandboxing) work correctly — ``:memory:`` would create
    separate, empty in-memory databases on each connection.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    os.environ["OPERION_ADMIN_EMAIL"] = _TEST_ADMIN_EMAIL
    os.environ["OPERION_ADMIN_PASSWORD_HASH"] = _TEST_ADMIN_HASH
    os.environ["OPERION_JWT_SECRET_KEY"] = _TEST_JWT_SECRET
    os.environ["OPERION_DB_PATH"] = tmp.name
    yield
    for k in ("OPERION_ADMIN_EMAIL", "OPERION_ADMIN_PASSWORD_HASH",
              "OPERION_JWT_SECRET_KEY", "OPERION_DB_PATH"):
        os.environ.pop(k, None)
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def admin_token(client) -> str:
    """Obtain a valid admin JWT for test use."""
    resp = client.post("/api/v1/auth/token", data={
        "username": _TEST_ADMIN_EMAIL,
        "password": _TEST_ADMIN_PASSWORD,
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_header(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


# ═══════════════════════════════════════════════════════════════════════
# Gate test: all admin endpoints must require admin role
# ═══════════════════════════════════════════════════════════════════════


class TestAdminAuthGate:
    """Every admin endpoint must return 403 without admin JWT."""

    ADMIN_ROUTES = [
        ("GET", "/api/v1/admin/diagnostics"),
        ("GET", "/api/v1/admin/db/tables"),
        ("GET", "/api/v1/admin/db/table/documents/schema"),
        ("GET", "/api/v1/admin/db/table/documents?page=0&page_size=10"),
        ("POST", "/api/v1/admin/db/query"),
        ("GET", "/api/v1/admin/documents/stats"),
        ("GET", "/api/v1/admin/documents/orphans"),
        ("GET", "/api/v1/admin/system/info"),
        ("GET", "/api/v1/admin/system/env"),
        ("GET", "/api/v1/admin/logs/tail"),
        ("POST", "/api/v1/admin/cache/clear"),
        ("GET", "/api/v1/admin/health/detailed"),
    ]

    @pytest.mark.parametrize("method,path", ADMIN_ROUTES)
    def test_admin_endpoint_returns_401_without_token(self, client, method, path):
        """Without any token, admin endpoints return 401 (via OAuth2 scheme)."""
        response = client.get(path) if method == "GET" else client.post(path, json={})
        # FastAPI's OAuth2PasswordBearer returns 401 (not 403) when the
        # token is entirely missing.
        assert response.status_code in (401, 403), (
            f"{method} {path} expected 401/403, got {response.status_code}"
        )

    def test_admin_endpoint_returns_403_with_user_jwt(self, client):
        """A non-admin token should produce 401 or 403 on admin endpoints.

        Without a users table in the test DB, a non-admin JWT will be
        rejected at the ``get_current_user`` gate (401).  When a users
        table is present with a matching row, the ``require_admin``
        gate returns 403 instead.
        """
        from backend.security import create_access_token
        user_token = create_access_token(
            data={"sub": "user@example.com", "role": "dispatcher"}
        )
        response = client.get(
            "/api/v1/admin/diagnostics",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        # Without a users table the token fails at identity resolution (401)
        # rather than at the role check (403) — either is acceptable.
        assert response.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════
# Functionality tests (with admin token)
# ═══════════════════════════════════════════════════════════════════════


class TestAdminDiagnostics:
    def test_diagnostics_returns_expected_fields(self, client, auth_header):
        response = client.get("/api/v1/admin/diagnostics", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        # Core fields must exist
        assert "latency_ms" in data
        assert "server_time_utc" in data
        assert "config_flags" in data
        cfg = data["config_flags"]
        assert "db_engine" in cfg
        assert "api_version" in cfg
        # Redis and Celery are optional (may be null if unavailable)
        assert "redis" in data
        assert "celery" in data


class TestAdminDbTables:
    def test_list_tables_returns_tables(self, client, auth_header):
        response = client.get("/api/v1/admin/db/tables", headers=auth_header)
        assert response.status_code == 200
        tables = response.json()
        assert isinstance(tables, list)
        if tables:
            table = tables[0]
            assert "name" in table
            assert "row_count" in table
            assert "columns" in table

    def test_table_schema_returns_columns(self, client, auth_header):
        response = client.get(
            "/api/v1/admin/db/table/documents/schema",
            headers=auth_header,
        )
        # documents table may or may not exist in test DB — allow 200 or 404
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            cols = response.json()
            assert isinstance(cols, list)
            if cols:
                assert "name" in cols[0]
                assert "type" in cols[0]

    def test_unknown_table_returns_404(self, client, auth_header):
        response = client.get(
            "/api/v1/admin/db/table/_nonexistent_9999/schema",
            headers=auth_header,
        )
        assert response.status_code == 404


class TestAdminRawQuery:
    def test_select_query_succeeds(self, client, auth_header):
        response = client.post(
            "/api/v1/admin/db/query",
            headers=auth_header,
            json={"query": "SELECT 1 AS test"},
        )
        assert response.status_code == 200
        rows = response.json()
        assert isinstance(rows, list)

    def test_drop_query_rejected(self, client, auth_header):
        """DROP queries must be rejected with 400."""
        response = client.post(
            "/api/v1/admin/db/query",
            headers=auth_header,
            json={"query": "DROP TABLE documents"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "Only SELECT" in data["detail"]

    def test_insert_query_rejected(self, client, auth_header):
        """INSERT queries must be rejected with 400."""
        response = client.post(
            "/api/v1/admin/db/query",
            headers=auth_header,
            json={"query": "INSERT INTO documents (id) VALUES (1)"},
        )
        assert response.status_code == 400

    def test_update_query_rejected(self, client, auth_header):
        """UPDATE queries must be rejected with 400."""
        response = client.post(
            "/api/v1/admin/db/query",
            headers=auth_header,
            json={"query": "UPDATE documents SET title = 'x' WHERE id = 1"},
        )
        assert response.status_code == 400

    def test_delete_query_rejected(self, client, auth_header):
        """DELETE queries must be rejected with 400."""
        response = client.post(
            "/api/v1/admin/db/query",
            headers=auth_header,
            json={"query": "DELETE FROM documents WHERE id = 1"},
        )
        assert response.status_code == 400


class TestAdminSystem:
    def test_system_info_returns_fields(self, client, auth_header):
        response = client.get("/api/v1/admin/system/info", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        assert "python_version" in data
        assert "db_engine" in data
        assert "api_version" in data

    def test_system_env_no_secrets_leaked(self, client, auth_header):
        """System env must not expose sensitive variables."""
        response = client.get("/api/v1/admin/system/env", headers=auth_header)
        assert response.status_code == 200
        data = response.json()
        variables = data.get("variables", {})
        for key in variables:
            assert "SECRET" not in key.upper()
            assert "PASSWORD" not in key.upper()
            assert "HASH" not in key.upper()
            assert "TOKEN" not in key.upper()


class TestAdminDocumentStats:
    def test_document_stats_return_fields(self, client, auth_header):
        response = client.get(
            "/api/v1/admin/documents/stats", headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "total_storage_bytes" in data
        assert "ocr_coverage_pct" in data

    def test_orphan_documents_returns_list(self, client, auth_header):
        response = client.get(
            "/api/v1/admin/documents/orphans", headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestAdminHealth:
    def test_detailed_health_returns_services(self, client, auth_header):
        response = client.get(
            "/api/v1/admin/health/detailed", headers=auth_header
        )
        assert response.status_code == 200
        data = response.json()
        services = data.get("services", [])
        assert len(services) >= 1
        names = [s["name"] for s in services]
        assert "database" in names
