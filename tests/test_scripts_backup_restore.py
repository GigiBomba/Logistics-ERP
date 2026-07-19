"""Tests for scripts/restore_data_from_backup.py — backup and restore logic."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, PropertyMock, patch

import pytest


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_expensive_imports():
    """Mock heavy/blocking imports that restore_data_from_backup needs."""
    with (
        patch("scripts.restore_data_from_backup.load_dotenv"),
        patch("scripts.restore_data_from_backup.Config"),
        patch("scripts.restore_data_from_backup.DatabaseManager"),
        patch("scripts.restore_data_from_backup.data_path", return_value="/fake/backups"),
    ):
        yield


# ── get_latest_backup ─────────────────────────────────────────────────────


class TestGetLatestBackup:
    def test_returns_latest_backup_file(self):
        with patch("scripts.restore_data_from_backup.glob.glob") as mock_glob:
            mock_glob.return_value = [
                "/fake/backups/backup_2026-01-01.db",
                "/fake/backups/backup_2026-07-15.db",
                "/fake/backups/backup_2026-06-01.db",
            ]

            from scripts.restore_data_from_backup import get_latest_backup

            result = get_latest_backup()
            assert result == "/fake/backups/backup_2026-07-15.db"

    def test_sys_exit_when_no_backups(self):
        with patch("scripts.restore_data_from_backup.glob.glob") as mock_glob:
            mock_glob.return_value = []

            from scripts.restore_data_from_backup import get_latest_backup

            with pytest.raises(SystemExit) as exc:
                get_latest_backup()
            assert exc.value.code == 1

    def test_single_backup_file(self):
        with patch("scripts.restore_data_from_backup.glob.glob") as mock_glob:
            mock_glob.return_value = ["/fake/backups/single.db"]

            from scripts.restore_data_from_backup import get_latest_backup

            result = get_latest_backup()
            assert result == "/fake/backups/single.db"


# ── table_exists ───────────────────────────────────────────────────────────


class TestTableExists:
    def test_returns_true_when_table_exists(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = (1,)

        from scripts.restore_data_from_backup import table_exists

        assert table_exists(conn, "trips") is True
        conn.execute.assert_called_once_with(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", ("trips",)
        )

    def test_returns_false_when_table_missing(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = None

        from scripts.restore_data_from_backup import table_exists

        assert table_exists(conn, "ghost_table") is False


# ── copy_table ─────────────────────────────────────────────────────────────


class TestCopyTable:
    def test_copies_rows_without_extra_columns(self):
        src = MagicMock()
        dst = MagicMock()
        src.execute.return_value.fetchall.return_value = [
            (1, "row1"),
            (2, "row2"),
        ]
        columns = ["id", "name"]
        placeholders = ["?", "?"]

        from scripts.restore_data_from_backup import copy_table

        copy_table(src, dst, "test_table", columns, placeholders, extra_columns=None)

        # copy_table converts rows to lists via list(row)
        assert dst.execute.call_count == 2
        dst.execute.assert_any_call(
            'INSERT OR IGNORE INTO "test_table" (id, name) VALUES (?, ?)',
            [1, "row1"],
        )
        dst.execute.assert_any_call(
            'INSERT OR IGNORE INTO "test_table" (id, name) VALUES (?, ?)',
            [2, "row2"],
        )

    def test_copies_rows_with_extra_columns(self):
        src = MagicMock()
        dst = MagicMock()
        src.execute.return_value.fetchall.return_value = [
            (1, "row1"),
        ]
        columns = ["id", "name"]
        placeholders = ["?", "?"]

        from scripts.restore_data_from_backup import copy_table

        copy_table(src, dst, "test_table", columns, placeholders,
                    extra_columns={"company_id": 42})

        dst.execute.assert_called_once_with(
            'INSERT OR IGNORE INTO "test_table" (id, name, company_id) VALUES (?, ?, ?)',
            [1, "row1", 42],
        )

    def test_skips_when_no_rows(self, capsys):
        src = MagicMock()
        dst = MagicMock()
        src.execute.return_value.fetchall.return_value = []

        from scripts.restore_data_from_backup import copy_table

        copy_table(src, dst, "empty_table", ["id"], ["?"], extra_columns=None)

        dst.execute.assert_not_called()
        captured = capsys.readouterr()
        assert "0 rows" in captured.out

    def test_continues_on_insert_error(self, capsys):
        src = MagicMock()
        dst = MagicMock()
        src.execute.return_value.fetchall.return_value = [
            (1, "good"),
            (2, "bad"),
        ]
        dst.execute.side_effect = [None, Exception("UNIQUE constraint")]

        from scripts.restore_data_from_backup import copy_table

        copy_table(src, dst, "test_table", ["id", "name"], ["?", "?"],
                    extra_columns=None)

        assert dst.execute.call_count == 2
        captured = capsys.readouterr()
        assert "skipped row" in captured.out

    def test_reports_row_count(self, capsys):
        src = MagicMock()
        dst = MagicMock()
        src.execute.return_value.fetchall.return_value = [
            (1,),
            (2,),
            (3,),
        ]

        from scripts.restore_data_from_backup import copy_table

        copy_table(src, dst, "t", ["id"], ["?"], extra_columns=None)

        captured = capsys.readouterr()
        assert "3 rows copied" in captured.out


# ── main() ─────────────────────────────────────────────────────────────────


def _make_main_mocks():
    """Create a realistic mock stack for main() tests.

    Returns (mock_db, mock_src) with sensible defaults so that the
    company/user seed passes and the backup table loop gracefully does
    nothing (all source table checks return None → table not found).
    """
    mock_db = MagicMock()
    # First fetchone call → existing company (id=1)
    # Second fetchone call → existing user (id=1, email)
    # All subsequent fetchone calls → None (table_exists returns False)
    mock_db.conn.execute.return_value.fetchone.side_effect = [
        (1,),  # existing company → no insert
        (1, "admin@test.com"),  # existing user → no insert
    ]

    mock_src = MagicMock()
    # fetchone for table_exists: always return None (table not found in backup)
    mock_src.execute.return_value.fetchone.return_value = None
    mock_src.execute.return_value.fetchall.return_value = []

    return mock_db, mock_src


class TestMain:
    def test_main_seeds_company_when_missing(self):
        mock_db = MagicMock()
        # No existing company → returns None
        # No existing user → returns None
        mock_db.conn.execute.return_value.fetchone.side_effect = [
            None,  # no company → insert
            None,  # no user → insert if credentials present
        ]

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect") as mock_sqlite,
            patch("scripts.restore_data_from_backup.os.environ.get",
                  side_effect=lambda k, d="": {"OPERION_ADMIN_EMAIL": "admin@test.com",
                                                "OPERION_ADMIN_PASSWORD_HASH": "$2b$12$abc"}.get(k, d)),
        ):
            mock_src = MagicMock()
            mock_sqlite.return_value = mock_src
            # table_exists returns False for all tables in backup
            mock_src.execute.return_value.fetchone.return_value = None
            mock_src.execute.return_value.fetchall.return_value = []

            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0

            # Company insert should have been called because no company existed
            insert_calls = [c for c in mock_db.conn.execute.call_args_list
                            if "INSERT INTO companies" in str(c)]
            assert len(insert_calls) > 0

    def test_main_skips_company_when_exists(self):
        mock_db, mock_src = _make_main_mocks()

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect", return_value=mock_src),
        ):
            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0

            # Should not have inserted a new company
            insert_calls = [c for c in mock_db.conn.execute.call_args_list
                            if "INSERT INTO companies" in str(c)]
            assert len(insert_calls) == 0

    def test_main_skips_data_tables_not_in_backup(self, capsys):
        mock_db, mock_src = _make_main_mocks()

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect", return_value=mock_src),
        ):
            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0
            captured = capsys.readouterr()
            assert "not found in backup" in captured.out

    def test_main_skips_data_tables_not_in_target(self, capsys):
        # Instead of relying on side_effect which gets exhausted, use a
        # function that returns different values based on call count.
        call_count = [0]

        def fetchone_side_effect(*_a, **_kw):
            idx = call_count[0]
            call_count[0] += 1
            if idx < 2:  # first 2 calls: company + user seed
                return (1,)
            # remaining calls: table_exists(target) → return None (table missing)
            return None

        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.side_effect = fetchone_side_effect

        mock_src = MagicMock()
        mock_src.execute.return_value.fetchone.return_value = (1,)  # table exists in src
        mock_src.execute.return_value.fetchall.return_value = []

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect", return_value=mock_src),
        ):
            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0
            captured = capsys.readouterr()
            assert "not found in target" in captured.out

    def test_main_creates_admin_user_when_missing(self):
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.side_effect = [
            (1,),  # existing company
            None,  # no existing user → should create
        ]

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect") as mock_sqlite,
            patch("scripts.restore_data_from_backup.os.environ.get",
                  side_effect=lambda k, d="": {"OPERION_ADMIN_EMAIL": "admin@test.com",
                                                "OPERION_ADMIN_PASSWORD_HASH": "plainpass"}.get(k, d)),
        ):
            mock_src = MagicMock()
            mock_sqlite.return_value = mock_src
            mock_src.execute.return_value.fetchone.return_value = None
            mock_src.execute.return_value.fetchall.return_value = []

            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0

            # Should have tried to insert the admin user
            insert_calls = [c for c in mock_db.conn.execute.call_args_list
                            if "INSERT INTO users" in str(c)]
            assert len(insert_calls) > 0

    def test_main_skips_admin_user_when_no_credentials(self, capsys):
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.side_effect = [
            (1,),  # existing company
            None,  # no user found
        ]

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect") as mock_sqlite,
            patch("scripts.restore_data_from_backup.os.environ.get",
                  side_effect=lambda k, d="": ""),  # no credentials
        ):
            mock_src = MagicMock()
            mock_sqlite.return_value = mock_src
            mock_src.execute.return_value.fetchone.return_value = None
            mock_src.execute.return_value.fetchall.return_value = []

            from scripts.restore_data_from_backup import main

            rc = main()
            assert rc == 0
            captured = capsys.readouterr()
            assert "No admin credentials" in captured.out

    def test_main_closes_connections(self):
        mock_db = MagicMock()
        mock_db.conn.execute.return_value.fetchone.side_effect = [
            (1,),
            (1, "admin@test.com"),
        ]

        with (
            patch("scripts.restore_data_from_backup.DatabaseManager", return_value=mock_db),
            patch("scripts.restore_data_from_backup.get_latest_backup",
                  return_value="/fake/backup.db"),
            patch("scripts.restore_data_from_backup.sqlite3.connect") as mock_sqlite,
        ):
            mock_src = MagicMock()
            mock_sqlite.return_value = mock_src
            mock_src.execute.return_value.fetchone.return_value = None
            mock_src.execute.return_value.fetchall.return_value = []

            from scripts.restore_data_from_backup import main

            main()

            mock_db.close.assert_called_once()
            mock_src.close.assert_called_once()


# ── Module structure ───────────────────────────────────────────────────────


class TestModuleStructure:
    def test_module_importable(self):
        import scripts.restore_data_from_backup as mod

        assert hasattr(mod, "get_latest_backup")
        assert hasattr(mod, "table_exists")
        assert hasattr(mod, "copy_table")
        assert hasattr(mod, "main")

    def test_backup_dir_defined(self):
        import scripts.restore_data_from_backup as mod

        assert hasattr(mod, "BACKUP_DIR")
        assert mod.BACKUP_DIR is not None
