"""Tests for repositories.user_repository — list, create, deactivate.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from database.tenant_context import clear_context, set_request_context
from repositories.user_repository import UserRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> UserRepository:
    return UserRepository(db)


@pytest.fixture(autouse=True)
def _clean_tenant_context():
    """Clear tenant context after each test so state does not leak."""
    yield
    clear_context()


# ── helpers ──────────────────────────────────────────────────────────


def _company(db: InMemoryDB, **kw) -> int:
    """Insert a company row directly and return its id."""
    d = dict(company_name="Test Company", subscription_tier="starter")
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(
        f"INSERT INTO companies ({cols}) VALUES ({vals})", list(d.values())
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _user(db: InMemoryDB, **kw) -> int:
    """Insert a user row directly and return its id."""
    d = dict(
        email="user@example.com",
        password_hash="$2b$12$abcdefgh123456",
        role="dispatcher",
        display_name="Test User",
        is_active=1,
        company_id=None,
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO users ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


# ── list_users ───────────────────────────────────────────────────────


class TestListUsers:
    def test_returns_all_users(self, db, repo):
        _user(db, email="alice@test.com")
        _user(db, email="bob@test.com")
        users = repo.list_users()
        assert len(users) == 2

    def test_ordering_by_role_then_email(self, db, repo):
        _user(db, email="zee@test.com", role="admin")
        _user(db, email="abe@test.com", role="dispatcher")
        _user(db, email="ann@test.com", role="admin")
        _user(db, email="sam@test.com", role="manager")
        users = repo.list_users()
        # roles ASC, then email ASC within each role group
        expected_order = [
            ("admin", "ann@test.com"),
            ("admin", "zee@test.com"),
            ("dispatcher", "abe@test.com"),
            ("manager", "sam@test.com"),
        ]
        assert len(users) == len(expected_order)
        for u, (exp_role, exp_email) in zip(users, expected_order):
            assert u["role"] == exp_role
            assert u["email"] == exp_email

    def test_empty_list_when_no_users(self, repo):
        assert repo.list_users() == []

    def test_excludes_password_hash(self, db, repo):
        _user(db, email="secret@test.com", password_hash="should-not-leak")
        users = repo.list_users()
        assert "password_hash" not in users[0]

    def test_company_filtering(self, db, repo):
        _company(db, id=101)
        _company(db, id=102)
        set_request_context(company_id=101, role="dispatcher")
        _user(db, email="in@test.com", company_id=101)
        _user(db, email="out@test.com", company_id=102)
        users = repo.list_users()
        assert len(users) == 1
        assert users[0]["email"] == "in@test.com"

    def test_admin_sees_all_companies(self, db, repo):
        _company(db, id=101)
        _company(db, id=102)
        set_request_context(company_id=101, role="admin")  # admins are not scoped
        _user(db, email="c1@test.com", company_id=101)
        _user(db, email="c2@test.com", company_id=102)
        users = repo.list_users()
        assert len(users) == 2

    def test_returns_relevant_columns(self, db, repo):
        _user(db, email="cols@test.com")
        users = repo.list_users()
        row = users[0]
        assert set(row.keys()) == {"id", "email", "role", "display_name", "is_active", "created_at"}


# ── create_user ──────────────────────────────────────────────────────


class TestCreateUser:
    def test_creates_and_returns_id(self, db, repo):
        uid = repo.create_user(
            email="new@test.com",
            password_hash="$2b$12$hashvalue",
            role="dispatcher",
            display_name="New User",
        )
        assert isinstance(uid, int)
        assert uid > 0
        row = db.conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        assert row is not None
        assert row["email"] == "new@test.com"
        assert row["display_name"] == "New User"

    def test_sets_all_fields_correctly(self, db, repo):
        uid = repo.create_user(
            email="fields@test.com",
            password_hash="p4ssw0rd_hash",
            role="admin",
            display_name="Admin User",
        )
        row = db.conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["email"] == "fields@test.com"
        assert row["password_hash"] == "p4ssw0rd_hash"
        assert row["role"] == "admin"
        assert row["display_name"] == "Admin User"

    def test_sets_is_active_to_one_by_default(self, db, repo):
        uid = repo.create_user(
            email="active@test.com",
            password_hash="hash",
            role="dispatcher",
            display_name="Active",
        )
        row = db.conn.execute("SELECT is_active FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["is_active"] == 1

    def test_sets_role_correctly(self, db, repo):
        for role in ("admin", "dispatcher", "manager", "viewer"):
            uid = repo.create_user(
                email=f"{role}@test.com",
                password_hash="hash",
                role=role,
                display_name=role.title(),
            )
            row = db.conn.execute("SELECT role FROM users WHERE id = ?", (uid,)).fetchone()
            assert row["role"] == role

    def test_assigns_company_id_from_context(self, db, repo):
        _company(db, id=105)
        set_request_context(company_id=105, role="dispatcher")
        uid = repo.create_user(
            email="company@test.com",
            password_hash="hash",
            role="dispatcher",
            display_name="Company User",
        )
        row = db.conn.execute("SELECT company_id FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["company_id"] == 105

    def test_no_company_id_when_unscoped(self, db, repo):
        """Admin/unscoped users do not get an automatic company_id."""
        uid = repo.create_user(
            email="nocompany@test.com",
            password_hash="hash",
            role="admin",
            display_name="No Company",
        )
        row = db.conn.execute("SELECT company_id FROM users WHERE id = ?", (uid,)).fetchone()
        # company_id column is nullable; should be NULL (None in Python)
        assert row["company_id"] is None

    def test_duplicate_email_raises(self, db, repo):
        _user(db, email="dup@test.com")
        with pytest.raises(Exception):
            repo.create_user(
                email="dup@test.com",
                password_hash="other_hash",
                role="dispatcher",
                display_name="Duplicate",
            )

    def test_empty_email_allowed_once(self, db, repo):
        """An empty string is a valid (non-null) email value, but only one."""
        repo.create_user(
            email="",
            password_hash="hash",
            role="dispatcher",
            display_name="Empty Email",
        )
        # A second empty email would violate the UNIQUE constraint
        with pytest.raises(Exception):
            repo.create_user(
                email="",
                password_hash="hash2",
                role="admin",
                display_name="Second Empty",
            )

    def test_empty_display_name(self, db, repo):
        uid = repo.create_user(
            email="empty_display@test.com",
            password_hash="hash",
            role="dispatcher",
            display_name="",
        )
        row = db.conn.execute("SELECT display_name FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["display_name"] == ""


# ── deactivate_user ──────────────────────────────────────────────────


class TestDeactivateUser:
    def test_sets_is_active_to_false(self, db, repo):
        uid = _user(db, is_active=1)
        repo.deactivate_user(uid)
        row = db.conn.execute("SELECT is_active FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["is_active"] == 0

    def test_does_not_delete_row(self, db, repo):
        uid = _user(db, is_active=1)
        repo.deactivate_user(uid)
        row = db.conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        assert row is not None  # row still exists

    def test_nonexistent_user_does_not_raise(self, repo):
        repo.deactivate_user(99999)  # should not crash

    def test_idempotent(self, db, repo):
        uid = _user(db, is_active=0)  # already inactive
        repo.deactivate_user(uid)     # deactivate again
        row = db.conn.execute("SELECT is_active FROM users WHERE id = ?", (uid,)).fetchone()
        assert row["is_active"] == 0  # stays inactive

    def test_negative_id_does_not_raise(self, repo):
        repo.deactivate_user(-1)  # should not crash

    def test_company_scoped_deactivation(self, db, repo):
        _company(db, id=101)
        _company(db, id=102)
        set_request_context(company_id=101, role="dispatcher")
        u1 = _user(db, email="in_scope@test.com", company_id=101, is_active=1)
        _user(db, email="out_of_scope@test.com", company_id=102, is_active=1)
        repo.deactivate_user(u1)
        row = db.conn.execute("SELECT is_active FROM users WHERE id = ?", (u1,)).fetchone()
        assert row["is_active"] == 0
        # The other company's user is unaffected — we cannot query
        # it through the scoped repo, but the raw DB still sees it.
        other = db.conn.execute(
            "SELECT is_active FROM users WHERE email = ?", ("out_of_scope@test.com",)
        ).fetchone()
        assert other["is_active"] == 1

    def test_returns_none(self, db, repo):
        uid = _user(db, is_active=1)
        result = repo.deactivate_user(uid)
        assert result is None
