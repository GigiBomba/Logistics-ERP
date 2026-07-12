"""Concurrency tests: registration and auth under parallel execution.

All tests use an in-memory SQLite database (``make_db``) so they are
fast and isolated.  No FastAPI TestClient is used — threads operate
directly on the database via ``InMemoryDB``.

Fire-and-forget concurrency patterns (``ThreadPoolExecutor``) match
the sibling file ``test_concurrency_db_write.py``.
"""

import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


@pytest.fixture(autouse=True)
def _ensure_jwt_secret():
    """Ensure JWT_SECRET_KEY is always set, even if other test modules pop it."""
    os.environ["OPERION_JWT_SECRET_KEY"] = "test-secret-key-32-chars-for-test!!"
    os.environ.setdefault("OPERION_ENV", "test")

from tests.test_helpers import make_db

pytestmark = pytest.mark.concurrency


class TestConcurrencyRegistration:
    """Concurrent registration scenarios with in-memory DB."""

    @pytest.fixture
    def db(self):
        return make_db()

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_display_name_column(db):
        """Add the ``display_name`` column to the users table if it does
        not already exist (added by migration in production but not
        always present in ``:memory:`` test databases)."""
        try:
            db.conn.execute(
                "ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''"
            )
        except Exception:
            pass  # column already exists

    # ── tests ────────────────────────────────────────────────────────────────

    def test_concurrent_unique_registrations(self, db):
        """Multiple threads registering different emails — all succeed."""
        from backend.security import hash_password

        self._ensure_display_name_column(db)

        errors = []
        lock = threading.Lock()

        def register(email):
            try:
                hashed = hash_password("securepass123")
                db.conn.execute(
                    "INSERT INTO companies (company_name, subscription_tier) "
                    "VALUES (?, 'starter')",
                    (f"Company {email}",),
                )
                company_id = db.conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                db.conn.execute(
                    "INSERT INTO users "
                    "(email, password_hash, role, company_id, display_name, "
                    " is_active) "
                    "VALUES (?, ?, 'manager', ?, 'User', 1)",
                    (email, hashed, company_id),
                )
                db.conn.commit()
            except Exception as e:
                with lock:
                    errors.append(str(e))

        emails = [f"concurrent{i:03d}@test.com" for i in range(10)]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(register, e) for e in emails]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, (
            f"Errors during concurrent registration: {errors}"
        )

        # Verify all users were created
        for email in emails:
            row = db.conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            assert row is not None, (
                f"User {email} was not created"
            )

    def test_concurrent_same_email_registration(self, db):
        """Multiple threads trying to register the same email — only one
        succeeds due to the UNIQUE constraint on ``users.email``."""
        from backend.security import hash_password

        self._ensure_display_name_column(db)

        success_count = [0]
        error_count = [0]
        lock = threading.Lock()

        def register():
            try:
                hashed = hash_password("securepass123")
                db.conn.execute(
                    "INSERT INTO companies (company_name, subscription_tier) "
                    "VALUES ('Same Email Corp', 'starter')"
                )
                company_id = db.conn.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]
                db.conn.execute(
                    "INSERT INTO users "
                    "(email, password_hash, role, company_id, display_name, "
                    " is_active) "
                    "VALUES ('same@test.com', ?, 'manager', ?, 'User', 1)",
                    (hashed, company_id),
                )
                db.conn.commit()
                with lock:
                    success_count[0] += 1
            except Exception:
                with lock:
                    error_count[0] += 1

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(register) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        # Only one should succeed due to UNIQUE constraint on users.email
        assert success_count[0] == 1, (
            f"Expected 1 success, got {success_count[0]}"
        )
        assert error_count[0] == 9, (
            f"Expected 9 failures, got {error_count[0]}"
        )

    def test_concurrent_token_generation(self, db):
        """Multiple threads generating refresh tokens — all tokens are
        unique (64 bytes of cryptographically secure random data)."""
        from backend.security import generate_refresh_token

        tokens = []
        lock = threading.Lock()

        def generate():
            token = generate_refresh_token()
            with lock:
                tokens.append(token)

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(generate) for _ in range(20)]
            for f in as_completed(futures):
                f.result()

        # All tokens should be unique
        assert len(tokens) == len(set(tokens)), (
            f"Expected 20 unique tokens, got {len(set(tokens))} "
            f"unique from {len(tokens)} total"
        )
        # Each token is 128 hex chars (64 bytes)
        for t in tokens:
            assert len(t) == 128, (
                f"Expected 128-char hex token, got {len(t)} chars"
            )

    def test_concurrent_user_creation_in_same_company(self, db):
        """Multiple threads creating users in the same company — all
        succeed because emails are unique."""
        from backend.security import hash_password

        self._ensure_display_name_column(db)

        # Create company first
        db.conn.execute(
            "INSERT INTO companies (company_name, subscription_tier) "
            "VALUES ('Shared Corp', 'starter')"
        )
        db.conn.commit()
        company_id = db.conn.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        errors = []
        lock = threading.Lock()

        def create_user(email):
            try:
                hashed = hash_password("pass123456")
                db.conn.execute(
                    "INSERT INTO users "
                    "(email, password_hash, role, company_id, display_name, "
                    " is_active) "
                    "VALUES (?, ?, 'dispatcher', ?, 'User', 1)",
                    (email, hashed, company_id),
                )
                db.conn.commit()
            except Exception as e:
                with lock:
                    errors.append(str(e))

        emails = [f"user{i:03d}@shared.com" for i in range(10)]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_user, e) for e in emails]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0, (
            f"Errors during concurrent user creation: {errors}"
        )
        for email in emails:
            row = db.conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            assert row is not None, (
                f"User {email} was not created"
            )

    def test_concurrent_token_refresh_race(self, db):
        """Multiple threads refreshing (consuming) the same refresh token
        — only one thread succeeds; the rest get ``None``.

        This simulates the race condition in a token rotation scenario
        where two requests attempt to use the same refresh token
        simultaneously.
        """
        from backend.api.v1.auth import _refresh_store, _store_refresh

        # Store a refresh token
        token_data = {
            "email": "race@test.com",
            "role": "manager",
            "expires_at": 9999999999,
        }
        token_hash = hashlib.sha256(
            "race-refresh-token".encode()
        ).hexdigest()
        _store_refresh(token_hash, token_data)

        # Verify it exists
        assert _refresh_store.get(token_hash) is not None, (
            "Token should have been stored"
        )

        # Simulate concurrent pop (what happens in the refresh endpoint)
        pops = []
        lock = threading.Lock()

        def try_pop():
            # Direct dict.pop — same as the in-memory path of
            # _consume_refresh without the lock (for a more aggressive
            # race).  We use dict.pop here because _consume_refresh
            # serialises with _refresh_consumed_lock.
            result = _refresh_store.pop(token_hash, None)
            with lock:
                pops.append(result)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(try_pop) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        # Only one thread should get the token payload
        non_none = [p for p in pops if p is not None]
        assert len(non_none) == 1, (
            f"Expected 1 successful pop, got {len(non_none)} "
            f"({sum(1 for p in pops if p is None)} got None)"
        )

        # Verify the payload is correct
        assert non_none[0] == token_data, (
            f"Popped data does not match stored data"
        )
