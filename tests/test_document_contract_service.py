"""Tests for ContractService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.document.contract_service import ContractService


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(repo_mock):
    return ContractService(repo_mock)


def test_create_contract(service):
    service._repo.create_contract.return_value = 42
    cid = service.create_contract(
        doc_id=1, client_id=100, contract_type="transport",
        start_date="2026-01-01", end_date="2027-01-01",
        value_eur=10000, payment_terms="Net 30",
        auto_renewal=True, renewal_notice_days=30,
        notes="Test contract",
    )
    assert cid == 42
    service._repo.create_contract.assert_called_once()
    args = service._repo.create_contract.call_args[0]
    assert args[0] == 1  # doc_id
    assert args[1] == 100  # client_id
    assert args[2] == "transport"


def test_get_contracts(service):
    service._repo.get_contracts.return_value = [{"id": 1}, {"id": 2}]
    result = service.get_contracts(client_id=100, status="active")
    assert result == [{"id": 1}, {"id": 2}]
    service._repo.get_contracts.assert_called_with(100, "active")


def test_get_contract(service):
    service._repo.get_contract_by_id.return_value = {"id": 1, "status": "active"}
    result = service.get_contract(1)
    assert result["id"] == 1
    assert result["status"] == "active"


def test_get_contract_not_found(service):
    service._repo.get_contract_by_id.return_value = None
    assert service.get_contract(999) is None


def test_update_contract_status(service):
    service.update_contract_status(1, "signed")
    service._repo.update_contract.assert_called_once()
    args = service._repo.update_contract.call_args[1]
    assert args["status"] == "signed"


def test_get_expiring_contracts(service):
    service._repo.get_expiring_contracts.return_value = [{"id": 1, "end_date": "2026-07-01"}]
    result = service.get_expiring_contracts(30)
    assert result == [{"id": 1, "end_date": "2026-07-01"}]
    service._repo.get_expiring_contracts.assert_called_with(30)
