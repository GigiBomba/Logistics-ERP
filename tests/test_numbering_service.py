"""Tests for NumberingService — delegation, format resolution, lazy repos, real DB."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from services.numbering_service import NumberingService
from tests.test_helpers import make_db


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def inv_repo_mock():
    return MagicMock()


@pytest.fixture
def prof_repo_mock():
    return MagicMock()


@pytest.fixture
def rec_repo_mock():
    return MagicMock()


@pytest.fixture
def service(db_mock):
    return NumberingService(db_mock)


@pytest.fixture
def service_with_mock_repos(service, inv_repo_mock, prof_repo_mock, rec_repo_mock):
    """Return a NumberingService with all three internal repos replaced by mocks."""
    service._inv_repo = inv_repo_mock
    service._prof_repo = prof_repo_mock
    service._rec_repo = rec_repo_mock
    return service


# ── next_invoice_number ──────────────────────────────────────────────

def test_next_invoice_number_delegates(service_with_mock_repos, inv_repo_mock):
    """next_invoice_number calls InvoiceRepository.get_next_number with the given format_key."""
    inv_repo_mock.get_next_number.return_value = "INV-2026-0042"
    result = service_with_mock_repos.next_invoice_number(format_key="inv_seq")
    inv_repo_mock.get_next_number.assert_called_once_with(format_key="inv_seq")
    assert result == "INV-2026-0042"


def test_next_invoice_number_default_format(service_with_mock_repos, inv_repo_mock):
    """next_invoice_number uses the default INV_DEFAULT_FMT when no format_key is passed."""
    from repositories.invoice_repository import DEFAULT_INVOICE_FORMAT_KEY
    inv_repo_mock.get_next_number.return_value = "INV-2026-0001"
    result = service_with_mock_repos.next_invoice_number()
    inv_repo_mock.get_next_number.assert_called_once_with(format_key=DEFAULT_INVOICE_FORMAT_KEY)
    assert result == "INV-2026-0001"


# ── next_proforma_number ─────────────────────────────────────────────

def test_next_proforma_number_delegates(service_with_mock_repos, prof_repo_mock):
    """next_proforma_number calls ProformaRepository.get_next_number."""
    from repositories.proforma_repository import DEFAULT_PROFORMA_FORMAT_KEY
    prof_repo_mock.get_next_number.return_value = "PROF-2026-0003"
    result = service_with_mock_repos.next_proforma_number()
    prof_repo_mock.get_next_number.assert_called_once_with(format_key=DEFAULT_PROFORMA_FORMAT_KEY)
    assert result == "PROF-2026-0003"


# ── next_receipt_number ──────────────────────────────────────────────

def test_next_receipt_number_delegates(service_with_mock_repos, rec_repo_mock):
    """next_receipt_number calls ReceiptRepository.get_next_number."""
    from repositories.receipt_repository import DEFAULT_FORMAT_KEY
    rec_repo_mock.get_next_number.return_value = "RCT-2026-000184"
    result = service_with_mock_repos.next_receipt_number()
    rec_repo_mock.get_next_number.assert_called_once_with(format_key=DEFAULT_FORMAT_KEY)
    assert result == "RCT-2026-000184"


# ── resolve_invoice_format_key ───────────────────────────────────────

def test_resolve_invoice_format_key_match(service):
    """resolve_invoice_format_key returns the correct key when display text matches."""
    key = service.resolve_invoice_format_key("INV-2026-0001", current_key="inv_year_seq")
    assert key == "inv_year_seq"

    key = service.resolve_invoice_format_key("INV-000042", current_key="inv_year_seq")
    assert key == "inv_seq"

    key = service.resolve_invoice_format_key("2026-INV-0001", current_key="inv_year_seq")
    assert key == "year_inv_seq"


def test_resolve_invoice_format_key_no_match(service):
    """resolve_invoice_format_key returns current_key when no match found."""
    key = service.resolve_invoice_format_key("NON-EXISTENT-LABEL", current_key="inv_year_seq")
    assert key == "inv_year_seq"

    key = service.resolve_invoice_format_key("", current_key="fallback")
    assert key == "fallback"


# ── available_invoice_formats ────────────────────────────────────────

def test_available_invoice_formats(service):
    """available_invoice_formats returns all display labels."""
    labels = service.available_invoice_formats()
    assert isinstance(labels, list)
    assert "INV-2026-0001" in labels
    assert "INV-000042" in labels
    assert "2026-INV-0001" in labels
    assert len(labels) == 3


# ── Lazy initialization ──────────────────────────────────────────────

def test_repos_are_lazily_initialized(db_mock):
    """Internal repo attributes are None until first access via the lazy getters."""
    svc = NumberingService(db_mock)
    assert svc._inv_repo is None
    assert svc._prof_repo is None
    assert svc._rec_repo is None

    # Accessing next_invoice_number should trigger lazy init
    with patch.object(svc, "_get_inv_repo", wraps=svc._get_inv_repo) as spy:
        svc.next_invoice_number()
        spy.assert_called_once()
    assert svc._inv_repo is not None


def test_different_repos_are_independent(db_mock):
    """Each lazy getter returns a different repository instance."""
    svc = NumberingService(db_mock)
    inv = svc._get_inv_repo()
    prof = svc._get_prof_repo()
    rec = svc._get_rec_repo()
    assert inv is not prof
    assert inv is not rec
    assert prof is not rec
    # Verify they are the correct types
    from repositories.invoice_repository import InvoiceRepository
    from repositories.proforma_repository import ProformaRepository
    from repositories.receipt_repository import ReceiptRepository
    assert isinstance(inv, InvoiceRepository)
    assert isinstance(prof, ProformaRepository)
    assert isinstance(rec, ReceiptRepository)


# ── Integration: real DB ─────────────────────────────────────────────

def test_all_methods_with_real_db():
    """Exercise all public methods against a real in-memory database."""
    db = make_db()
    svc = NumberingService(db)

    # Invoice number — inserts into the invoices table drive MAX(id) + 1
    num = svc.next_invoice_number()
    assert isinstance(num, str)
    assert num.startswith("INV-")

    # Proforma number
    pnum = svc.next_proforma_number()
    assert isinstance(pnum, str)
    assert pnum.startswith("PROF-")

    # Receipt number
    rnum = svc.next_receipt_number()
    assert isinstance(rnum, str)
    assert rnum.startswith("RCT-")

    # Format resolution
    key = svc.resolve_invoice_format_key("INV-2026-0001", current_key="fallback")
    assert key == "inv_year_seq"

    key = svc.resolve_invoice_format_key("bogus", current_key="fallback")
    assert key == "fallback"

    # Available formats
    labels = svc.available_invoice_formats()
    assert len(labels) == 3
    assert all(isinstance(l, str) for l in labels)
