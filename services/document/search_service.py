"""Search service — advanced search, FTS5 search, and metadata queries."""

from __future__ import annotations

from typing import Any

from repositories.document_repository import DocumentRepository

class SearchService:

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    def advanced_search(self, query: str = "", category: str = "",
                        entity_type: str = "", entity_id: int | None = None,
                        date_from: str = "", date_to: str = "",
                        mime_type: str = "", tag: str = "",
                        order: str = "uploaded_at DESC",
                        page: int = 0, page_size: int = 20) -> dict[str, Any]:
        offset = page * page_size
        total = self._repo.advanced_search_count(
            query, category, entity_type, entity_id,
            date_from, date_to, mime_type, tag,
        )
        rows = self._repo.advanced_search(
            query, category, entity_type, entity_id,
            date_from, date_to, mime_type, tag,
            order, page_size, offset,
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def search(self, query: str = "", category: str = "",
               entity_type: str = "", entity_id: int | None = None,
               order: str = "uploaded_at DESC",
               page: int = 0, page_size: int = 20) -> dict[str, Any]:
        offset = page * page_size
        total = self._repo.search_count(query, category, entity_type, entity_id)
        rows = self._repo.search(
            query, category, entity_type, entity_id, order,
            page_size, offset,
        )
        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def fts_search(self, query: str = "", category: str = "",
                   entity_type: str = "", order: str = "uploaded_at DESC",
                   page: int = 0, page_size: int = 20) -> dict[str, Any]:
        offset = page * page_size
        if query:
            total = self._repo.fts_search_count(query, category, entity_type)
            rows = self._repo.fts_search(query, category, entity_type, order,
                                         page_size, offset)
        else:
            total = self._repo.advanced_search_count(query, category, entity_type)
            rows = self._repo.advanced_search(query, category, entity_type,
                                              order=order, limit=page_size,
                                              offset=offset)
        return {
            "items": rows, "total": total, "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def get_categories(self) -> list[dict[str, Any]]:
        return self._repo.count_by_category()

    def get_all_tags(self) -> list[str]:
        return self._repo.get_all_tags()

    def get_entity_types(self) -> list[str]:
        return self._repo.get_distinct_entity_types()

    def get_mime_types(self) -> list[str]:
        return self._repo.get_distinct_mime_types()
