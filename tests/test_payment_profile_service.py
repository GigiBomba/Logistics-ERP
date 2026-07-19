"""Comprehensive unit tests for PaymentProfileService.

Tests cover CRUD operations, company-scoping through the service layer,
delegation to PaymentProfileRepository, and all specified edge cases.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.payment_profile_service import PaymentProfileService


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_repo() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(mock_db: MagicMock, mock_repo: MagicMock) -> PaymentProfileService:
    svc = PaymentProfileService(mock_db)
    # Replace the real repo with our mock
    svc._repo = mock_repo
    return svc


# ── Sample data ──────────────────────────────────────────────────────


def _sample_profile(**overrides) -> dict:
    data = {
        "profile_name": "Supplier Corp",
        "recipient_type": "supplier",
        "bank_name": "Test Bank",
        "bank_account": "1234567890",
        "bank_code": "BARC12345",
        "bank_bic": "BARCGB22",
        "iban": "GB29NWBK60161331926819",
        "payment_reference": "INV-001",
        "contact_name": "John Contact",
        "contact_email": "john@supplier.com",
        "contact_phone": "+44012345678",
        "notes": "Test notes",
        "is_active": True,
    }
    data.update(overrides)
    return data


# ─────────────────────────────────────────────────────────────────────
# get_all
# ─────────────────────────────────────────────────────────────────────


class TestGetAll:
    def test_returns_list_of_profiles(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_all.return_value = [
            {"id": 1, "profile_name": "A"},
            {"id": 2, "profile_name": "B"},
        ]
        result = service.get_all()
        assert len(result) == 2
        assert result[0]["profile_name"] == "A"

    def test_passes_include_inactive(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(include_inactive=True)
        mock_repo.get_all.assert_called_once_with(include_inactive=True, limit=500)

    def test_passes_limit(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(limit=10)
        mock_repo.get_all.assert_called_once_with(include_inactive=False, limit=10)

    def test_passes_company_id_though_not_used(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(company_id=42)
        # company_id accepted but not forwarded to repo
        mock_repo.get_all.assert_called_once_with(include_inactive=False, limit=500)

    def test_returns_empty_list(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_all.return_value = []
        result = service.get_all()
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# get_by_id
# ─────────────────────────────────────────────────────────────────────


class TestGetById:
    def test_returns_profile(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_by_id.return_value = {"id": 1, "profile_name": "Test"}
        result = service.get_by_id(1)
        assert result is not None
        assert result["profile_name"] == "Test"

    def test_returns_none_for_missing(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_by_id.return_value = None
        result = service.get_by_id(99999)
        assert result is None

    def test_calls_repo_with_correct_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_by_id(42)
        mock_repo.get_by_id.assert_called_once_with(42)

    def test_accepts_company_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_by_id(1, company_id=7)
        mock_repo.get_by_id.assert_called_once_with(1)


# ─────────────────────────────────────────────────────────────────────
# search
# ─────────────────────────────────────────────────────────────────────


class TestSearch:
    def test_returns_matching_profiles(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.search.return_value = [
            {"id": 1, "profile_name": "Supplier ABC"},
        ]
        result = service.search("ABC")
        assert len(result) == 1
        assert result[0]["profile_name"] == "Supplier ABC"

    def test_passes_query_and_limit(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.search("test query", limit=15)
        mock_repo.search.assert_called_once_with("test query", limit=15)

    def test_returns_empty_when_no_match(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.search.return_value = []
        result = service.search("nonexistent")
        assert result == []

    def test_accepts_company_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.search("query", company_id=99)
        mock_repo.search.assert_called_once_with("query", limit=20)


# ─────────────────────────────────────────────────────────────────────
# get_active_by_type
# ─────────────────────────────────────────────────────────────────────


class TestGetActiveByType:
    def test_filters_by_recipient_type(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_active_by_type.return_value = [
            {"id": 1, "recipient_type": "government"},
        ]
        result = service.get_active_by_type("government")
        assert len(result) == 1
        assert result[0]["recipient_type"] == "government"

    def test_passes_type_and_limit(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_active_by_type("supplier", limit=25)
        mock_repo.get_active_by_type.assert_called_once_with("supplier", limit=25)

    def test_default_limit_is_500(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_active_by_type("custom")
        mock_repo.get_active_by_type.assert_called_once_with("custom", limit=500)

    def test_returns_empty(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_active_by_type.return_value = []
        result = service.get_active_by_type("nonexistent_type")
        assert result == []


# ─────────────────────────────────────────────────────────────────────
# create
# ─────────────────────────────────────────────────────────────────────


class TestCreate:
    def test_returns_new_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.create.return_value = 42
        result = service.create(_sample_profile())
        assert result == 42

    def test_passes_data_to_repo(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = _sample_profile(profile_name="New Profile")
        service.create(data)
        mock_repo.create.assert_called_once_with(data)

    def test_accepts_company_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = _sample_profile()
        service.create(data, company_id=7)
        mock_repo.create.assert_called_once_with(data)

    def test_create_empty_data(self, service: PaymentProfileService, mock_repo: MagicMock):
        """Repo is responsible for validation; service passes through."""
        service.create({})
        mock_repo.create.assert_called_once_with({})


# ─────────────────────────────────────────────────────────────────────
# update
# ─────────────────────────────────────────────────────────────────────


class TestUpdate:
    def test_updates_profile(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.update(1, {"profile_name": "Updated"})
        mock_repo.update.assert_called_once_with(1, {"profile_name": "Updated"})

    def test_accepts_company_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.update(1, {"profile_name": "New"}, company_id=7)
        mock_repo.update.assert_called_once_with(1, {"profile_name": "New"})

    def test_update_with_full_data(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = _sample_profile(profile_name="Changed")
        service.update(5, data)
        mock_repo.update.assert_called_once_with(5, data)


# ─────────────────────────────────────────────────────────────────────
# delete
# ─────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_deletes_profile(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.delete(1)
        mock_repo.delete.assert_called_once_with(1)

    def test_accepts_company_id(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.delete(1, company_id=7)
        mock_repo.delete.assert_called_once_with(1)

    def test_delete_nonexistent(self, service: PaymentProfileService, mock_repo: MagicMock):
        """Service does not raise on non-existent profiles."""
        service.delete(99999)
        mock_repo.delete.assert_called_once_with(99999)


# ─────────────────────────────────────────────────────────────────────
# Company scoping — service accepts company_id but does not filter
# ─────────────────────────────────────────────────────────────────────


class TestCompanyScoping:
    """The service layer currently accepts company_id but does not apply it.
    The repository handles company scoping via context.  These tests confirm
    the service passes through correctly.
    """

    def test_get_all_with_company(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(company_id=10)
        # repo.get_all does not accept company_id
        import inspect
        sig = inspect.signature(mock_repo.get_all)
        assert "company_id" not in sig.parameters

    def test_get_by_id_with_company(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_by_id(1, company_id=10)
        mock_repo.get_by_id.assert_called_once_with(1)

    def test_get_active_by_type_with_company(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_active_by_type("supplier", limit=50)
        mock_repo.get_active_by_type.assert_called_once_with("supplier", limit=50)

    def test_create_with_company_context(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = _sample_profile()
        service.create(data, company_id=7)
        mock_repo.create.assert_called_once_with(data)

    def test_update_with_company_context(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.update(1, {"profile_name": "X"}, company_id=7)
        mock_repo.update.assert_called_once_with(1, {"profile_name": "X"})

    def test_delete_with_company_context(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.delete(1, company_id=7)
        mock_repo.delete.assert_called_once_with(1)


# ─────────────────────────────────────────────────────────────────────
# Edge cases
# ─────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_get_by_id_with_zero(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_by_id.return_value = None
        result = service.get_by_id(0)
        assert result is None

    def test_get_by_id_with_none(self, service: PaymentProfileService, mock_repo: MagicMock):
        # The service does not guard; it passes None to the repo.
        service.get_by_id(None)  # type: ignore[arg-type]
        mock_repo.get_by_id.assert_called_once_with(None)

    def test_update_with_empty_dict(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.update(1, {})
        mock_repo.update.assert_called_once_with(1, {})

    def test_create_returns_id_zero(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.create.return_value = 0
        result = service.create(_sample_profile())
        assert result == 0

    def test_search_empty_query(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.search("", limit=10)
        mock_repo.search.assert_called_once_with("", limit=10)

    def test_get_all_large_limit(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(limit=10_000)
        mock_repo.get_all.assert_called_once_with(include_inactive=False, limit=10_000)


# ─────────────────────────────────────────────────────────────────────
# Validation — service passes through; repo is responsible
# ─────────────────────────────────────────────────────────────────────


class TestValidationPassthrough:
    """The service does no validation itself; it delegates to the repo.
    These tests ensure repo validation errors propagate correctly.
    """

    def test_create_invalid_data_raises_from_repo(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.create.side_effect = ValueError("Invalid column: bad_col")
        with pytest.raises(ValueError, match="Invalid column"):
            service.create({"bad_col": "value"})

    def test_update_invalid_data_raises_from_repo(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.update.side_effect = ValueError("Invalid column: bad_col")
        with pytest.raises(ValueError, match="Invalid column"):
            service.update(1, {"bad_col": "value"})

    def test_repo_exception_on_get_all(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.get_all.side_effect = RuntimeError("DB connection lost")
        with pytest.raises(RuntimeError, match="DB connection lost"):
            service.get_all()

    def test_repo_exception_on_delete(self, service: PaymentProfileService, mock_repo: MagicMock):
        mock_repo.delete.side_effect = RuntimeError("DB error")
        with pytest.raises(RuntimeError, match="DB error"):
            service.delete(1)


# ─────────────────────────────────────────────────────────────────────
# Service-repo exact delegation
# ─────────────────────────────────────────────────────────────────────


class TestDelegation:
    """Verify that every public service method delegates exactly to the repo."""

    def test_get_all_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_all(include_inactive=True, limit=10)
        mock_repo.get_all.assert_called_once_with(include_inactive=True, limit=10)

    def test_get_by_id_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_by_id(7)
        mock_repo.get_by_id.assert_called_once_with(7)

    def test_search_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.search("term", limit=5)
        mock_repo.search.assert_called_once_with("term", limit=5)

    def test_get_active_by_type_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.get_active_by_type("contractor", limit=3)
        mock_repo.get_active_by_type.assert_called_once_with("contractor", limit=3)

    def test_create_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = _sample_profile()
        service.create(data)
        mock_repo.create.assert_called_once_with(data)

    def test_update_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        data = {"profile_name": "Updated"}
        service.update(1, data)
        mock_repo.update.assert_called_once_with(1, data)

    def test_delete_delegates(self, service: PaymentProfileService, mock_repo: MagicMock):
        service.delete(1)
        mock_repo.delete.assert_called_once_with(1)
