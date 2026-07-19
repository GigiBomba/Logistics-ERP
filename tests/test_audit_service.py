"""Tests for services.audit_service — audit logging service.

All repository dependencies are mocked; no database required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.audit_service import AuditService


class TestAuditService:
    """Unit tests for AuditService (all collaborators mocked)."""

    # ------------------------------------------------------------------
    # Per-test setup — construct service with mocked db
    # ------------------------------------------------------------------

    def setup_method(self):
        """Create a fresh AuditService instance with a mocked db."""
        self.mock_db = MagicMock()
        self.service = AuditService(self.mock_db)

    # ------------------------------------------------------------------
    # log() — basic field delegation
    # ------------------------------------------------------------------

    def test_log_delegates_to_repo_with_all_fields(self):
        """log() calls repo.log_event with every expected parameter."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log(
                event_type="trip.created",
                entity_type="trip",
                entity_id="42",
                user_id=10,
                data={"key": "value"},
                company_id=5,
            )

            mock_repo_cls.assert_called_once_with(self.mock_db)
            mock_repo.log_event.assert_called_once_with(
                event_type="trip.created",
                entity_type="trip",
                entity_id="42",
                data={"key": "value"},
                user_id=10,
                company_id=5,
            )

    def test_log_converts_entity_id_to_string(self):
        """log() converts an integer entity_id to string before passing to repo."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", 123)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["entity_id"] == "123"

    def test_log_uses_defaults_when_optional_fields_omitted(self):
        """log() applies default user_id=0, company_id=0, data={}."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1")

            mock_repo.log_event.assert_called_once_with(
                event_type="test.event",
                entity_type="test",
                entity_id="1",
                data={},
                user_id=0,
                company_id=0,
            )

    def test_log_converts_none_data_to_empty_dict(self):
        """log() passes an empty dict when data is None."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", data=None)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["data"] == {}

    def test_log_passes_str_entity_id_unchanged(self):
        """log() preserves a string entity_id without modification."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "already-string")

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["entity_id"] == "already-string"

    def test_log_passes_empty_string_entity_id(self):
        """log() accepts an empty string for entity_id (edge case)."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "")

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["entity_id"] == ""

    def test_log_handles_zero_user_id(self):
        """log() accepts user_id=0 (system/unknown user)."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", user_id=0)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["user_id"] == 0

    def test_log_handles_negative_user_id(self):
        """log() accepts a negative user_id (edge case)."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", user_id=-1)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["user_id"] == -1

    # ------------------------------------------------------------------
    # Correlation ID enrichment
    # ------------------------------------------------------------------

    def test_log_adds_correlation_id_when_available(self):
        """log() enriches data with _correlation_id when the middleware provides one."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch(
                "backend.middleware.correlation_middleware.get_correlation_id",
                return_value="cid-abc123",
            ),
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log(
                "test.event",
                "test",
                "1",
                data={"existing_key": "original_value"},
            )

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["data"]["_correlation_id"] == "cid-abc123"
            assert kwargs["data"]["existing_key"] == "original_value"

    def test_log_adds_correlation_id_with_no_existing_data(self):
        """log() adds _correlation_id even when no initial data dict is passed."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch(
                "backend.middleware.correlation_middleware.get_correlation_id",
                return_value="cid-xyz",
            ),
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1")

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["data"] == {"_correlation_id": "cid-xyz"}

    def test_log_skips_correlation_id_when_middleware_unavailable(self):
        """log() silently skips correlation enrichment on ImportError (default)."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", data={"key": "val"})

            _args, kwargs = mock_repo.log_event.call_args
            assert "_correlation_id" not in kwargs["data"]

    def test_log_skips_correlation_id_when_middleware_returns_none(self):
        """log() skips enrichment when get_correlation_id returns None."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch(
                "backend.middleware.correlation_middleware.get_correlation_id",
                return_value=None,
            ),
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", data={"key": "val"})

            _args, kwargs = mock_repo.log_event.call_args
            assert "_correlation_id" not in kwargs["data"]

    def test_log_skips_correlation_id_when_middleware_returns_empty(self):
        """log() skips enrichment when get_correlation_id returns empty string."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch(
                "backend.middleware.correlation_middleware.get_correlation_id",
                return_value="",
            ),
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", data={"key": "val"})

            _args, kwargs = mock_repo.log_event.call_args
            assert "_correlation_id" not in kwargs["data"]

    # ------------------------------------------------------------------
    # Data handling — non-serializable content
    # ------------------------------------------------------------------

    def test_log_passes_non_serializable_data_through(self):
        """log() passes non-serialisable objects in data (repo handles serialisation).

        The repository uses ``json.dumps(data, default=str)``, so objects
        with a ``__str__`` method are safe.  The service itself does not
        serialise — it just passes the dict through.
        """
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            class CustomObject:
                def __str__(self):
                    return "serialised-by-str"

            self.service.log(
                "test.event",
                "test",
                "1",
                data={"obj": CustomObject()},
            )

            _args, kwargs = mock_repo.log_event.call_args
            assert "obj" in kwargs["data"]
            assert str(kwargs["data"]["obj"]) == "serialised-by-str"

    def test_log_handles_complex_nested_data(self):
        """log() accepts deeply nested dict structures in data."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            data = {
                "level1": {
                    "level2": [1, 2, {"nested": True}],
                },
                "list": [{"a": 1}, {"b": 2}],
            }
            self.service.log("test.event", "test", "1", data=data)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["data"] == data

    def test_log_handles_data_with_none_values(self):
        """log() accepts data dicts containing None values."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1", data={"key": None})

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["data"]["key"] is None

    # ------------------------------------------------------------------
    # Error handling — AuditRepository failures
    # ------------------------------------------------------------------

    def test_log_does_not_crash_when_repo_raises(self):
        """log() catches repo exceptions and logs a warning instead of crashing."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch("services.audit_service.logger") as mock_logger,
        ):
            mock_repo = MagicMock()
            mock_repo.log_event.side_effect = RuntimeError("DB connection lost")
            mock_repo_cls.return_value = mock_repo

            # Should not raise
            self.service.log("test.event", "test", "1")

            mock_logger.warning.assert_called_once()
            msg = mock_logger.warning.call_args[0][0]
            assert "Audit logging failed" in msg

    def test_log_does_not_crash_when_repo_import_fails(self):
        """If AuditRepository itself cannot be imported, log() catches and warns."""
        with (
            patch(
                "repositories.audit_repository.AuditRepository",
                side_effect=ImportError("no module"),
            ),
            patch("services.audit_service.logger") as mock_logger,
        ):
            # Should not raise even though repo import failed
            self.service.log("test.event", "test", "1")

            mock_logger.warning.assert_called_once()

    def test_log_does_not_crash_when_db_is_problematic(self):
        """log() handles exceptions raised during AuditRepository construction."""
        mock_bad_db = MagicMock()
        bad_service = AuditService(mock_bad_db)

        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch("services.audit_service.logger") as mock_logger,
        ):
            mock_repo_cls.side_effect = TypeError("db object not compatible")

            bad_service.log("test.event", "test", "1")

            mock_logger.warning.assert_called_once()

    def test_log_handles_multiple_consecutive_failures(self):
        """log() handles multiple consecutive repo failures gracefully."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch("services.audit_service.logger") as mock_logger,
        ):
            mock_repo = MagicMock()
            mock_repo.log_event.side_effect = RuntimeError("fail")
            mock_repo_cls.return_value = mock_repo

            for _ in range(5):
                self.service.log("test.event", "test", "1")

            assert mock_logger.warning.call_count == 5

    # ------------------------------------------------------------------
    # Audit data fields for filtering support
    #
    # The AuditService currently only exposes log().  The repository
    # layer (AuditRepository.get_events) provides filtering by
    # event_type_prefix, and logging the correct fields here is what
    # makes that filtering meaningful.  These tests verify that the
    # write side stores the data needed for read-side filtering.
    # ------------------------------------------------------------------

    def test_log_stores_user_id_for_user_filtering(self):
        """Events logged with a user_id enable per-user filtering at the repo level."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("user.login", "user", "5", user_id=42)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["user_id"] == 42

    def test_log_stores_event_type_for_action_filtering(self):
        """The event_type field serves as the 'action' filter dimension."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("trip.deleted", "trip", "7", user_id=3)

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["event_type"] == "trip.deleted"

    def test_log_stores_timestamp_through_created_at_field(self):
        """The repository assigns ``created_at`` so events are date-range filterable."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1")

            # The repo's log_event sets created_at internally; the service
            # does not pass a timestamp itself — this test verifies the
            # delegation path is intact.
            mock_repo.log_event.assert_called_once()

    def test_log_stores_entity_type_for_resource_filtering(self):
        """entity_type enables filtering by resource kind."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("invoice.created", "invoice", "INV-101")

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["entity_type"] == "invoice"

    def test_log_uniqueness_across_multiple_calls(self):
        """Each log() call creates a separate event — no dedup at service level."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            for i in range(10):
                self.service.log("test.event", "test", str(i), user_id=i)

            assert mock_repo.log_event.call_count == 10

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_log_with_empty_event_type(self):
        """log() accepts an empty event_type (edge case)."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("", "", "")

            mock_repo.log_event.assert_called_once_with(
                event_type="",
                entity_type="",
                entity_id="",
                data={},
                user_id=0,
                company_id=0,
            )

    def test_log_with_large_data_payload(self):
        """log() accepts large data payloads."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            large_data = {f"key_{i}": f"value_{i}" for i in range(1000)}
            self.service.log("test.event", "test", "1", data=large_data)

            _args, kwargs = mock_repo.log_event.call_args
            assert len(kwargs["data"]) == 1000

    def test_log_with_special_characters_in_fields(self):
        """log() handles special characters in event_type, entity_type, and data."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log(
                "test.event.with.dots",
                "test-entity/2",
                "id@123",
                data={"message": "Line 1\nLine 2", "emoji": "🚚"},
            )

            _args, kwargs = mock_repo.log_event.call_args
            assert kwargs["event_type"] == "test.event.with.dots"
            assert kwargs["entity_type"] == "test-entity/2"
            assert kwargs["entity_id"] == "id@123"
            assert kwargs["data"]["emoji"] == "🚚"

    # ------------------------------------------------------------------
    # Repository delegation — the service creates AuditRepository(self.db)
    # ------------------------------------------------------------------

    def test_log_creates_repo_with_db(self):
        """log() instantiates AuditRepository with self.db each call."""
        with patch("repositories.audit_repository.AuditRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("test.event", "test", "1")

            mock_repo_cls.assert_called_once_with(self.mock_db)

    def test_log_debug_log_on_success(self):
        """On success, log() writes a debug message."""
        with (
            patch("repositories.audit_repository.AuditRepository") as mock_repo_cls,
            patch("services.audit_service.logger") as mock_logger,
        ):
            mock_repo = MagicMock()
            mock_repo_cls.return_value = mock_repo

            self.service.log("trip.created", "trip", "42", user_id=7)
            mock_logger.debug.assert_called_once()
            msg = mock_logger.debug.call_args[0][0]
            assert "Audit:" in msg
