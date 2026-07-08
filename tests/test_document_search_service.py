"""Tests for SearchService."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.document.search_service import SearchService


@pytest.fixture
def repo_mock():
    return MagicMock()


@pytest.fixture
def service(repo_mock):
    return SearchService(repo_mock)


def test_advanced_search(service):
    service._repo.advanced_search_count.return_value = 10
    service._repo.advanced_search.return_value = [{"id": 1}, {"id": 2}]

    result = service.advanced_search(query="test", category="invoices",
                                     entity_type="trip", entity_id=1,
                                     page=0, page_size=20)
    assert result["total"] == 10
    assert len(result["items"]) == 2
    assert result["page"] == 0
    assert result["page_size"] == 20
    assert result["total_pages"] == 1


def test_advanced_search_pagination(service):
    service._repo.advanced_search_count.return_value = 50
    service._repo.advanced_search.return_value = [{"id": i} for i in range(20)]

    result = service.advanced_search(page=1, page_size=20)
    assert result["total"] == 50
    assert result["page"] == 1
    assert result["total_pages"] == 3


def test_search(service):
    service._repo.search_count.return_value = 5
    service._repo.search.return_value = [{"id": 1}]

    result = service.search(query="test", category="general")
    assert result["total"] == 5
    assert result["items"] == [{"id": 1}]


def test_fts_search_with_query(service):
    service._repo.fts_search_count.return_value = 3
    service._repo.fts_search.return_value = [{"id": 1}]

    result = service.fts_search(query="invoice", page=0, page_size=20)
    assert result["total"] == 3


def test_fts_search_without_query(service):
    service._repo.advanced_search_count.return_value = 10
    service._repo.advanced_search.return_value = [{"id": 1}]

    result = service.fts_search(query="", page=0, page_size=20)
    assert result["total"] == 10
    service._repo.advanced_search.assert_called()


def test_get_categories(service):
    service._repo.count_by_category.return_value = [{"category": "invoices", "cnt": 5}]
    assert service.get_categories() == [{"category": "invoices", "cnt": 5}]


def test_get_all_tags(service):
    service._repo.get_all_tags.return_value = ["tag1", "tag2"]
    assert service.get_all_tags() == ["tag1", "tag2"]


def test_get_entity_types(service):
    service._repo.get_distinct_entity_types.return_value = ["trip", "truck"]
    assert service.get_entity_types() == ["trip", "truck"]


def test_get_mime_types(service):
    service._repo.get_distinct_mime_types.return_value = ["application/pdf"]
    assert service.get_mime_types() == ["application/pdf"]
