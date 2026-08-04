"""Freight load-board LIST endpoint — multi-tenant isolation (blueprint §6.3).

Endpoint under test: ``GET /api/v1/freight/loads``
(``backend/api/v1/freight_exchange.py``).

Rules enforced here (blueprint §6.3 + §1.8):
- the list is company-scoped: ``company_id`` is derived from the JWT only,
  never from a query param or the body;
- each company sees only loads returned for its own ``company_id``;
- the endpoint is gated by ``require_dispatcher``.

Uses the shared module-scoped fixtures from ``tests/security/conftest.py``
(client, auth_a, auth_b) and patches ``SearchEngineService`` so no real
provider connection is needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.common import Money
from models.freight_exchange_models import LoadSearchResult
from services.freight_exchange.search import SearchResultSet

_LOADS_URL = "/api/v1/freight/loads"


def _make_load(load_id: str, origin: str, destination: str) -> LoadSearchResult:
    now = datetime.now(timezone.utc)
    return LoadSearchResult(
        result_id=load_id,
        provider_id="timocom",
        provider_load_id=f"TIM-{load_id}",
        origin=origin,
        destination=destination,
        pickup_window=(now, now + timedelta(hours=6)),
        delivery_window=(now + timedelta(hours=24), now + timedelta(hours=48)),
        price=Money(amount="1500.00", currency="EUR"),
        distance_km=800.0,
        trailer_type="curtain",
        adr=False,
    )


class TestFreightLoadsCompanyIsolation:
    """Each company only sees loads scoped to its own JWT company_id."""

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_company_a_sees_only_company_a_loads(
        self, mock_search_cls: MagicMock, client, auth_a: dict,
    ) -> None:
        def _side_effect(company_id, filters, provider_ids=None):
            result_set = SearchResultSet()
            if company_id == 1:
                result_set.results = [
                    _make_load("LOAD-A-1", "Berlin", "Paris"),
                    _make_load("LOAD-A-2", "Munich", "Lyon"),
                ]
            return result_set

        mock_instance = MagicMock()
        mock_instance.search_loads = AsyncMock(side_effect=_side_effect)
        mock_search_cls.return_value = mock_instance

        resp = client.get(_LOADS_URL, headers=auth_a)
        assert resp.status_code == 200, f"Loads list failed: {resp.text}"
        ids = {item["id"] for item in resp.json()}
        assert ids == {"LOAD-A-1", "LOAD-A-2"}
        # Service was invoked with the JWT-derived company_id.
        assert mock_instance.search_loads.call_args.kwargs["company_id"] == 1

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_company_b_sees_only_company_b_loads(
        self, mock_search_cls: MagicMock, client, auth_b: dict,
    ) -> None:
        def _side_effect(company_id, filters, provider_ids=None):
            result_set = SearchResultSet()
            if company_id == 2:
                result_set.results = [
                    _make_load("LOAD-B-1", "Madrid", "Rome"),
                ]
            return result_set

        mock_instance = MagicMock()
        mock_instance.search_loads = AsyncMock(side_effect=_side_effect)
        mock_search_cls.return_value = mock_instance

        resp = client.get(_LOADS_URL, headers=auth_b)
        assert resp.status_code == 200
        ids = {item["id"] for item in resp.json()}
        assert ids == {"LOAD-B-1"}
        assert mock_instance.search_loads.call_args.kwargs["company_id"] == 2

    @patch("backend.api.v1.freight_exchange.SearchEngineService")
    def test_company_id_never_read_from_query_param(
        self, mock_search_cls: MagicMock, client, auth_a: dict,
    ) -> None:
        """A client-supplied company_id query param must be ignored."""
        mock_instance = MagicMock()
        mock_instance.search_loads = AsyncMock(return_value=SearchResultSet())
        mock_search_cls.return_value = mock_instance

        resp = client.get(
            f"{_LOADS_URL}?company_id=2",  # attempt to spoof tenant
            headers=auth_a,
        )
        assert resp.status_code == 200
        assert mock_instance.search_loads.call_args.kwargs["company_id"] == 1

    def test_unauthorized_requests_rejected(self, client) -> None:
        resp = client.get(_LOADS_URL)
        assert resp.status_code == 401
