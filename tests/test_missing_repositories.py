"""Tests for database tables without dedicated test coverage: companies, users, gps_telemetry.

All tests use a file-based SQLite database via DatabaseManager and exercise
the tables directly through SQL (no repository layer).
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from database.db_manager import DatabaseManager


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    """Create a temporary file-based DatabaseManager for testing.

    The fixture yields a fully initialised DatabaseManager connected to a
    unique temporary file.  After the test completes the file is removed.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    mgr = DatabaseManager(tmp.name)
    yield mgr
    mgr.close()
    os.unlink(tmp.name)


# ── Companies ─────────────────────────────────────────────────────────────────


class TestCompaniesTable:
    """Direct SQL tests for the ``companies`` table.

    The companies table stores multi-tenant company profiles with a
    subscription tier and active status flag.  It has *no* UNIQUE
    constraint on ``company_name``.
    """

    def test_create_company(self, db):
        """Insert a company and verify it can be read back."""
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)",
            ("Test Company",),
        )
        company_id = cursor.lastrowid
        assert company_id is not None and company_id > 0

        row = db.conn.execute(
            "SELECT id, company_name, subscription_tier, is_active "
            "FROM companies WHERE id = ?",
            (company_id,),
        ).fetchone()
        assert row is not None
        assert row["company_name"] == "Test Company"

    def test_default_subscription_tier(self, db):
        """A company created without subscription_tier defaults to 'starter'."""
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)",
            ("Default Tier Co",),
        )
        row = db.conn.execute(
            "SELECT subscription_tier FROM companies WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        assert row["subscription_tier"] == "starter"

    def test_deactivate_company(self, db):
        """Set is_active to 0 and verify the change is persisted."""
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)",
            ("Deactivatable Co",),
        )
        cid = cursor.lastrowid
        db.conn.execute("UPDATE companies SET is_active = 0 WHERE id = ?", (cid,))
        db.conn.commit()

        row = db.conn.execute(
            "SELECT is_active FROM companies WHERE id = ?", (cid,),
        ).fetchone()
        assert row["is_active"] == 0

    def test_company_name_is_unique_test(self, db):
        """company_name is NOT unique — two companies with the same name are allowed."""
        db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)", ("Duplicate Name",),
        )
        # Second insert with the same name must succeed (no UNIQUE constraint)
        db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)", ("Duplicate Name",),
        )
        db.conn.commit()

        rows = db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM companies WHERE company_name = ?",
            ("Duplicate Name",),
        ).fetchone()
        assert rows["cnt"] == 2

    def test_multiple_companies(self, db):
        """Insert three companies and verify all are readable."""
        for name in ["Alpha", "Beta", "Gamma"]:
            db.conn.execute(
                "INSERT INTO companies (company_name) VALUES (?)", (name,),
            )
        db.conn.commit()

        rows = db.conn.execute(
            "SELECT company_name FROM companies ORDER BY company_name",
        ).fetchall()
        assert len(rows) == 3
        assert [r["company_name"] for r in rows] == ["Alpha", "Beta", "Gamma"]


# ── Users ─────────────────────────────────────────────────────────────────────


class TestUsersTable:
    """Direct SQL tests for the ``users`` table.

    The users table stores authentication credentials, role, and a FK to
    the companies table.  Email addresses are UNIQUE.
    """

    @pytest.fixture
    def company_id(self, db):
        """Create a minimal company and return its id for FK references."""
        cursor = db.conn.execute(
            "INSERT INTO companies (company_name) VALUES (?)",
            ("User Test Co",),
        )
        db.conn.commit()
        return cursor.lastrowid

    def test_create_user(self, db, company_id):
        """Insert a user and verify it can be read back."""
        cursor = db.conn.execute(
            "INSERT INTO users (email, password_hash, role, company_id) "
            "VALUES (?, ?, ?, ?)",
            ("user@example.com", "hash123", "admin", company_id),
        )
        uid = cursor.lastrowid
        assert uid is not None and uid > 0

        row = db.conn.execute(
            "SELECT id, email, role, company_id, is_active "
            "FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        assert row is not None
        assert row["email"] == "user@example.com"
        assert row["role"] == "admin"
        assert row["company_id"] == company_id
        assert row["is_active"] == 1

    def test_email_unique_constraint(self, db, company_id):
        """Creating two users with the same email raises IntegrityError."""
        db.conn.execute(
            "INSERT INTO users (email, password_hash, company_id) "
            "VALUES (?, ?, ?)",
            ("dupe@example.com", "hash1", company_id),
        )
        db.conn.commit()

        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.conn.execute(
                "INSERT INTO users (email, password_hash, company_id) "
                "VALUES (?, ?, ?)",
                ("dupe@example.com", "hash2", company_id),
            )

    def test_user_role_default(self, db, company_id):
        """A user created without role defaults to 'dispatcher'."""
        cursor = db.conn.execute(
            "INSERT INTO users (email, password_hash, company_id) "
            "VALUES (?, ?, ?)",
            ("dispatcher@example.com", "hash", company_id),
        )
        row = db.conn.execute(
            "SELECT role FROM users WHERE id = ?", (cursor.lastrowid,),
        ).fetchone()
        assert row["role"] == "dispatcher"

    def test_user_with_company_fk(self, db, company_id):
        """Insert a user with a valid company FK and verify the join works."""
        cursor = db.conn.execute(
            "INSERT INTO users (email, password_hash, company_id) "
            "VALUES (?, ?, ?)",
            ("fkuser@example.com", "hash", company_id),
        )
        uid = cursor.lastrowid
        row = db.conn.execute(
            "SELECT u.email, c.company_name "
            "FROM users u "
            "JOIN companies c ON u.company_id = c.id "
            "WHERE u.id = ?",
            (uid,),
        ).fetchone()
        assert row["company_name"] == "User Test Co"

    def test_deactivate_user(self, db, company_id):
        """Set is_active to 0 and verify the change is persisted."""
        cursor = db.conn.execute(
            "INSERT INTO users (email, password_hash, company_id) "
            "VALUES (?, ?, ?)",
            ("deactivate@example.com", "hash", company_id),
        )
        uid = cursor.lastrowid
        db.conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (uid,))
        db.conn.commit()

        row = db.conn.execute(
            "SELECT is_active FROM users WHERE id = ?", (uid,),
        ).fetchone()
        assert row["is_active"] == 0

    def test_user_display_name(self, db, company_id):
        """Create a user with a display_name and read it back.

        The ``display_name`` column is added by a migration that runs during
        DatabaseManager initialisation, so it is available for new inserts.
        """
        cursor = db.conn.execute(
            "INSERT INTO users (email, password_hash, role, company_id, display_name) "
            "VALUES (?, ?, ?, ?, ?)",
            ("display@example.com", "hash", "dispatcher", company_id,
             "John Display"),
        )
        uid = cursor.lastrowid
        row = db.conn.execute(
            "SELECT display_name FROM users WHERE id = ?", (uid,),
        ).fetchone()
        assert row["display_name"] == "John Display"


# ── GPS Telemetry ─────────────────────────────────────────────────────────────


class TestGpsTelemetryTable:
    """Direct SQL tests for the ``gps_telemetry`` table.

    The GPS telemetry table stores real-time location data for trucks.
    The ``driver_id`` column is nullable (an optional reference).
    """

    GPS_COLS = ("truck_id", "latitude", "longitude", "speed_kmh", "recorded_at")

    def _seed_truck(self, db, truck_id):
        """Ensure a truck row exists to satisfy FK constraints."""
        db.conn.execute("PRAGMA foreign_keys=OFF")
        db.conn.execute(
            "INSERT OR IGNORE INTO trucks (id, plate_number) VALUES (?, ?)",
            (truck_id, f"TRUCK-{truck_id:04d}"),
        )
        db.conn.execute("PRAGMA foreign_keys=ON")
        db.conn.commit()

    def _insert(self, db, truck_id, lat, lon, speed, recorded_at):
        """Insert a GPS record and return the new row id."""
        db.conn.execute("PRAGMA foreign_keys=OFF")
        cursor = db.conn.execute(
            "INSERT INTO gps_telemetry "
            "(truck_id, latitude, longitude, speed_kmh, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (truck_id, lat, lon, speed, recorded_at),
        )
        db.conn.execute("PRAGMA foreign_keys=ON")
        return cursor.lastrowid

    def test_insert_gps_record(self, db):
        """Insert a GPS record and verify it can be read back."""
        self._seed_truck(db, 1)
        gid = self._insert(db, 1, 45.5, 25.3, 80.0, "2025-06-01T10:00:00")
        assert gid is not None and gid > 0

        row = db.conn.execute(
            "SELECT truck_id, latitude, longitude, speed_kmh "
            "FROM gps_telemetry WHERE id = ?",
            (gid,),
        ).fetchone()
        assert row["truck_id"] == 1
        assert row["latitude"] == pytest.approx(45.5)
        assert row["longitude"] == pytest.approx(25.3)
        assert row["speed_kmh"] == pytest.approx(80.0)

    def test_query_by_truck_id(self, db):
        """Insert records for multiple trucks and query by a specific truck."""
        for tid in (1, 2, 3):
            self._seed_truck(db, tid)
        records = [
            (1, 45.0, 25.0, 50.0, "2025-06-01T10:00:00"),
            (2, 46.0, 26.0, 60.0, "2025-06-01T10:00:00"),
            (1, 45.1, 25.1, 55.0, "2025-06-01T10:05:00"),
            (3, 47.0, 27.0, 70.0, "2025-06-01T10:00:00"),
            (2, 46.1, 26.1, 65.0, "2025-06-01T10:05:00"),
        ]
        for args in records:
            self._insert(db, *args)
        db.conn.commit()

        # Truck 1 should have 2 records
        rows = db.conn.execute(
            "SELECT id FROM gps_telemetry WHERE truck_id = ? ORDER BY id",
            (1,),
        ).fetchall()
        assert len(rows) == 2

        # Truck 2 should have 2 records
        rows = db.conn.execute(
            "SELECT id FROM gps_telemetry WHERE truck_id = ? ORDER BY id",
            (2,),
        ).fetchall()
        assert len(rows) == 2

        # Truck 3 should have 1 record
        rows = db.conn.execute(
            "SELECT id FROM gps_telemetry WHERE truck_id = ? ORDER BY id",
            (3,),
        ).fetchall()
        assert len(rows) == 1

    def test_query_by_time_range(self, db):
        """Insert records with different timestamps and query a time window."""
        self._seed_truck(db, 1)
        timestamps = [
            "2025-06-01T08:00:00",
            "2025-06-01T09:00:00",
            "2025-06-01T10:00:00",
            "2025-06-01T11:00:00",
            "2025-06-01T12:00:00",
        ]
        for ts in timestamps:
            self._insert(db, 1, 45.0, 25.0, 50.0, ts)
        db.conn.commit()

        rows = db.conn.execute(
            "SELECT recorded_at FROM gps_telemetry "
            "WHERE recorded_at >= ? AND recorded_at <= ? "
            "ORDER BY recorded_at",
            ("2025-06-01T09:30:00", "2025-06-01T11:30:00"),
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["recorded_at"] == "2025-06-01T10:00:00"
        assert rows[1]["recorded_at"] == "2025-06-01T11:00:00"

    def test_gps_null_driver_allowed(self, db):
        """Insert a GPS record with driver_id=NULL (optional field)."""
        self._seed_truck(db, 1)
        cursor = db.conn.execute(
            "INSERT INTO gps_telemetry "
            "(truck_id, latitude, longitude, driver_id, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (1, 45.0, 25.0, None, "2025-06-01T10:00:00"),
        )
        gid = cursor.lastrowid
        row = db.conn.execute(
            "SELECT driver_id FROM gps_telemetry WHERE id = ?", (gid,),
        ).fetchone()
        assert row["driver_id"] is None


# ── DatabaseManager Settings ──────────────────────────────────────────────────


class TestDatabaseManagerSettings:
    """Tests for :meth:`DatabaseManager.save_setting` / :meth:`DatabaseManager.get_setting`.

    Settings use a composite primary key ``(key, company_id)``, providing
    company-scoped key-value storage.  The FK to ``companies(id)`` means
    we must create parent companies before saving settings.
    """

    @pytest.fixture
    def company_1(self, db):
        """Create company id=1 (required by FK on settings)."""
        db.conn.execute(
            "INSERT INTO companies (id, company_name) VALUES (?, ?)",
            (1, "Company One"),
        )
        db.conn.commit()

    @pytest.fixture
    def company_2(self, db):
        """Create company id=2 (required by FK on settings)."""
        db.conn.execute(
            "INSERT INTO companies (id, company_name) VALUES (?, ?)",
            (2, "Company Two"),
        )
        db.conn.commit()

    def test_save_and_get_setting_with_company(self, db, company_1):
        """Save a setting scoped to a company and retrieve it."""
        from database.tenant_context import set_company_context
        set_company_context(1)
        db.save_setting("theme", "dark")
        result = db.get_setting("theme")
        assert result == "dark"
        set_company_context(None)

    def test_settings_isolated_per_company(self, db, company_1, company_2):
        """Settings saved for different companies are kept separate."""
        from database.tenant_context import set_company_context
        set_company_context(1)
        db.save_setting("language", "en")
        set_company_context(2)
        db.save_setting("language", "ro")

        set_company_context(1)
        assert db.get_setting("language") == "en"
        set_company_context(2)
        assert db.get_setting("language") == "ro"
        set_company_context(None)

    def test_get_setting_returns_none_for_missing_key(self, db, company_1):
        """Requesting a non-existent key returns None."""
        from database.tenant_context import set_company_context
        set_company_context(1)
        result = db.get_setting("nonexistent.key")
        assert result is None
        set_company_context(None)


# ── Backfill Safety ───────────────────────────────────────────────────────────


class TestBackfillSafety:
    """Verify that migration backfills do not overwrite existing data.

    DatabaseManager applies several backfills during initialisation
    (e.g. settings table composite PK migration, tenant table ``company_id``
    backfill).  These must not overwrite values that were explicitly set.
    """

    def test_setting_backfill_on_init(self, db):
        """Verify that the settings table migration ran and uses composite PK.

        After DatabaseManager.__init__ completes, the ``settings`` table
        should have a composite primary key of ``(key, company_id)``.
        """
        pk_info = db.conn.execute("PRAGMA table_info(settings)").fetchall()
        pk_cols = [r["name"] for r in pk_info if r["pk"] > 0]
        assert pk_cols == ["key", "company_id"], (
            f"Expected composite PK (key, company_id), got {pk_cols}"
        )

    def test_company_backfill_preserves_existing(self, db):
        """Backfill does not overwrite an explicit company_id on a record.

        We insert two rows — one with an explicit ``company_id=42`` and one
        with ``company_id=NULL`` — then manually run the same backfill SQL
        that DatabaseManager runs during migration.  The explicit value
        must be preserved while the NULL is backfilled to 1.
        """
        # Create parent companies so FK constraints are satisfied
        # (company_id=1 for the backfill target, company_id=42 for the explicit value)
        for cid in (1, 42):
            db.conn.execute(
                "INSERT INTO companies (id, company_name) VALUES (?, ?)",
                (cid, f"Backfill Co {cid}"),
            )
        db.conn.commit()

        # Insert a row with an explicit company_id and one without
        db.conn.execute(
            "INSERT INTO trips (truck_number, driver_name, client_name, "
            "distance_km, total_price_eur, start_date, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("TRUCK-001", "Driver A", "Client X", 100.0, 500.0,
             "2025-06-01", 42),
        )
        db.conn.execute(
            "INSERT INTO trips (truck_number, driver_name, client_name, "
            "distance_km, total_price_eur, start_date) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("TRUCK-002", "Driver B", "Client Y", 200.0, 1000.0,
             "2025-06-02"),
        )
        db.conn.commit()

        # Simulate the migration backfill
        db.conn.execute(
            "UPDATE trips SET company_id = 1 WHERE company_id IS NULL",
        )
        db.conn.commit()

        # Explicit company_id must be preserved
        row1 = db.conn.execute(
            "SELECT company_id FROM trips WHERE truck_number = ?",
            ("TRUCK-001",),
        ).fetchone()
        assert row1["company_id"] == 42, (
            f"Expected company_id=42, got {row1['company_id']}"
        )

        # NULL company_id must have been backfilled
        row2 = db.conn.execute(
            "SELECT company_id FROM trips WHERE truck_number = ?",
            ("TRUCK-002",),
        ).fetchone()
        assert row2["company_id"] == 1, (
            f"Expected company_id=1 after backfill, got {row2['company_id']}"
        )
