"""Tests for the anonymous error-reporting channel.

POST /api/v1/support/anonymous-error — NO auth required, rate-limited per IP
(10/hour), stores a PII-free digest locally in ``anonymous_error_reports``.
Deliberately NOT proxied to the internal support service.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

BASE = "/api/v1/support/anonymous-error"

# A real digest produced by error-reporting.ts ``buildReportDigest``
# (encodeURIComponent output — URL-safe marks + %XX escapes only).
_VALID_DIGEST = (
    "%5BFatal%20UI%20Error%5D%0A%0Aboom%0A%0A"
    "Component%20stack%3A%0A%20%20%20%20at%20App"
)


@pytest.fixture(scope="module", autouse=True)
def _set_env():
    """Point the app DB at a per-module temp SQLite file.

    Mirrors tests/test_api/test_waitlist_api.py: ``Config.DB_PATH`` is rebound
    explicitly because ``config`` is imported at collection time (before
    fixtures run), so setting ``OPERION_DB_PATH`` alone would not redirect the
    app DB.  The process-global DB singleton is dropped so ``init_db()``
    rebuilds it against this module's temp file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    # Snapshot the originals BEFORE overwriting them so teardown RESTORES
    # instead of popping (same discipline as tests/test_api/test_waitlist_api.py
    # and tests/test_scripts_backup_restore.py).  The old teardown popped
    # OPERION_DB_PATH/OPERION_ENV unconditionally, leaving them missing for
    # every later module in the worker: a subsequent import-time
    # ``load_dotenv(.env)`` (root ``main.py``, ``backend.main``,
    # ``scripts/restore_data_from_backup.py``, …) then re-created
    # ``OPERION_ENV=production`` + ``OPERION_API_KEY=<real key>`` from the
    # checked-in ``.env``, which cascaded 401
    # ``{"detail":"API key required","error_code":"auth/invalid-api-key"}``
    # failures across the later sync/settings suites.
    # (``monkeypatch`` cannot be used here: it is function-scoped and this
    # fixture is module-scoped.)
    _saved_env = {
        k: os.environ.get(k)
        for k in ("OPERION_DB_PATH", "OPERION_ENV", "OPERION_DB_ENGINE")
    }
    os.environ["OPERION_DB_PATH"] = tmp.name
    os.environ["OPERION_ENV"] = "development"
    from config import Config
    previous_db_path = Config.DB_PATH
    previous_db_engine = Config.DB_ENGINE
    os.environ["OPERION_DB_ENGINE"] = "sqlite"
    Config.DB_ENGINE = "sqlite"
    Config.DB_PATH = tmp.name
    from backend import dependencies as _deps
    if _deps._db_instance is not None:
        try:
            _deps._db_instance.close()
        except Exception:
            pass
        _deps._db_instance = None
    yield
    # Restore the env vars (pop ONLY when they were originally absent) …
    for k, v in _saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    # … and the Config-class attributes this fixture rebound, so the module
    # leaves no global state behind for later workers/tests.
    Config.DB_ENGINE = previous_db_engine
    Config.DB_PATH = previous_db_path
    if _deps._db_instance is not None:
        try:
            _deps._db_instance.close()
        except Exception:
            pass
        _deps._db_instance = None
    try:
        os.unlink(tmp.name)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset rate-limit state and empty the report table before each test."""
    from backend.utils.rate_limit import _fallback
    _fallback.clear()
    from backend.dependencies import init_db
    try:
        db = init_db()
        db.conn.execute("DELETE FROM anonymous_error_reports")
        db.conn.commit()
    except Exception:
        pass
    yield


@pytest.fixture
def app():
    """Bare FastAPI app with the v1 router and a REAL db dependency.

    No auth middleware and no auth dependency overrides — the anonymous-error
    endpoint must succeed without any credential.
    """
    from fastapi import FastAPI
    from backend.api.v1.router import api_v1_router
    from backend.dependencies import get_db, init_db

    application = FastAPI()
    application.include_router(api_v1_router)
    application.dependency_overrides[get_db] = lambda: init_db()
    return application


@pytest.fixture
def anon_client(app):
    """Unauthenticated TestClient — no Authorization / X-API-Key headers."""
    return TestClient(app, raise_server_exceptions=False)


def _count_reports() -> int:
    from backend.dependencies import init_db
    db = init_db()
    row = db.conn.execute(
        "SELECT COUNT(*) AS c FROM anonymous_error_reports"
    ).fetchone()
    return row["c"] if row else 0


class TestRecordAnonymousError:
    def test_accepts_valid_digest_without_auth(self, anon_client):
        """202 + row persisted — no token and no API key required."""
        resp = anon_client.post(BASE, json={"digest": _VALID_DIGEST})
        assert resp.status_code == 202
        assert resp.json() == {"status": "recorded"}
        assert _count_reports() == 1

    def test_stores_metadata_and_hashed_ip(self, anon_client):
        resp = anon_client.post(
            BASE,
            json={
                "digest": _VALID_DIGEST,
                "component_stack": "    at App",
                "url": "https://app.example.com/dash?utm_campaign=spring#top",
            },
        )
        assert resp.status_code == 202

        from backend.dependencies import init_db
        db = init_db()
        row = db.conn.execute(
            "SELECT digest, component_stack, url, ip_hash, created_at "
            "FROM anonymous_error_reports"
        ).fetchone()
        assert row is not None
        assert row["digest"] == _VALID_DIGEST
        assert row["component_stack"] == "    at App"
        # query string / fragment (potential PII) is stripped server-side
        assert row["url"] == "https://app.example.com/dash"
        assert row["ip_hash"]
        assert row["ip_hash"] != "127.0.0.1"  # never a raw IP
        assert row["created_at"]

    def test_rejects_missing_digest(self, anon_client):
        resp = anon_client.post(BASE, json={})
        assert resp.status_code == 422
        assert _count_reports() == 0

    def test_rejects_oversized_digest(self, anon_client):
        resp = anon_client.post(BASE, json={"digest": "A" * 5000})
        assert resp.status_code == 422
        assert _count_reports() == 0

    def test_rejects_raw_freeform_digest(self, anon_client):
        """The digest must be URL-encoded — raw whitespace/newlines (free-form
        PII smuggling) are rejected."""
        resp = anon_client.post(BASE, json={"digest": "[Fatal UI Error]\n\nboom"})
        assert resp.status_code == 422
        assert _count_reports() == 0

    def test_rejects_unknown_pii_fields(self, anon_client):
        """No free-form PII fields exist on this channel — extras are rejected."""
        resp = anon_client.post(
            BASE,
            json={"digest": _VALID_DIGEST, "email": "pii@example.com"},
        )
        assert resp.status_code == 422
        assert _count_reports() == 0

    def test_rate_limits_per_ip(self, anon_client):
        """10 reports/hour allowed; the 11th from the same IP is throttled."""
        for _ in range(10):
            resp = anon_client.post(BASE, json={"digest": _VALID_DIGEST})
            assert resp.status_code == 202

        resp = anon_client.post(BASE, json={"digest": _VALID_DIGEST})
        assert resp.status_code == 429
        assert _count_reports() == 10

    def test_rate_limit_applies_before_persistence(self, anon_client):
        """Throttled requests must NOT leave rows behind."""
        for _ in range(10):
            anon_client.post(BASE, json={"digest": _VALID_DIGEST})
        resp = anon_client.post(BASE, json={"digest": _VALID_DIGEST})
        assert resp.status_code == 429
        assert _count_reports() == 10