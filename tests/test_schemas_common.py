"""Tests for backend/schemas/common.py — PaginationParams, PaginatedResponse, ErrorResponse."""

from __future__ import annotations

from typing import List

import pytest
from pydantic import ValidationError

from backend.schemas.common import ErrorResponse, PaginatedResponse, PaginationParams


# ── PaginationParams ──────────────────────────────────────────────────────────


class TestPaginationParams:
    """page: int = 0, page_size: int = 20, extra="forbid"."""

    def test_defaults(self):
        inst = PaginationParams()
        assert inst.page == 0
        assert inst.page_size == 20

    @pytest.mark.parametrize(
        ("page", "page_size"),
        [
            (0, 1),
            (0, 100),
            (1, 50),
            (10, 20),
            (100, 10),
        ],
    )
    def test_valid_values(self, page: int, page_size: int):
        inst = PaginationParams(page=page, page_size=page_size)
        assert inst.page == page
        assert inst.page_size == page_size

    @pytest.mark.parametrize("page", [-1, -10, 0, 1, 100])
    def test_any_integer_page_accepted(self, page: int):
        """No ge/gt constraint — any int is accepted."""
        inst = PaginationParams(page=page)
        assert inst.page == page

    @pytest.mark.parametrize("page_size", [0, -1, 1, 50, 100, 200])
    def test_any_integer_page_size_accepted(self, page_size: int):
        """No ge/gt constraint — any int is accepted."""
        inst = PaginationParams(page_size=page_size)
        assert inst.page_size == page_size

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            PaginationParams(unknown_field="value")  # type: ignore[call-arg]


# ── PaginatedResponse ─────────────────────────────────────────────────────────


class TestPaginatedResponse:
    """Generic — items: List[T], total: int, total_pages: int, extra="forbid"."""

    def test_str_items(self):
        inst = PaginatedResponse[str](items=["a", "b"], total=2, total_pages=1)
        assert inst.items == ["a", "b"]
        assert inst.total == 2
        assert inst.total_pages == 1

    def test_int_items(self):
        inst = PaginatedResponse[int](items=[10, 20, 30], total=3, total_pages=1)
        assert inst.items == [10, 20, 30]

    def test_nested_model_items(self):
        inst = PaginatedResponse[PaginationParams](
            items=[PaginationParams(page=1, page_size=10)],
            total=1,
            total_pages=1,
        )
        assert len(inst.items) == 1
        assert inst.items[0].page == 1

    def test_empty_items(self):
        inst = PaginatedResponse[int](items=[], total=0, total_pages=0)
        assert inst.items == []

    def test_serialization_round_trip(self):
        original = PaginatedResponse[str](items=["x", "y"], total=2, total_pages=1)
        dumped = original.model_dump()
        restored = PaginatedResponse[str].model_validate(dumped)
        assert restored == original

    def test_extra_field_ignored(self):
        """PaginatedResponse uses extra='ignore', so unknown fields are dropped."""
        inst = PaginatedResponse[int](items=[], total=0, total_pages=0, bad_key=1)  # type: ignore[call-arg]
        assert "bad_key" not in inst.model_dump()

    @pytest.mark.parametrize("total", [-1, -100, 0, 100])
    def test_any_integer_total_accepted(self, total: int):
        """No ge constraint — any int is accepted."""
        inst = PaginatedResponse[int](items=[], total=total, total_pages=0)
        assert inst.total == total

    @pytest.mark.parametrize("total_pages", [-1, -5, 0, 5])
    def test_any_integer_total_pages_accepted(self, total_pages: int):
        """No ge constraint — any int is accepted."""
        inst = PaginatedResponse[int](items=[], total=0, total_pages=total_pages)
        assert inst.total_pages == total_pages


# ── ErrorResponse ─────────────────────────────────────────────────────────────


class TestErrorResponse:
    """detail: str (required), error_code: Optional[str] = None, extra="forbid"."""

    def test_minimal(self):
        inst = ErrorResponse(detail="Something went wrong")
        assert inst.detail == "Something went wrong"
        assert inst.error_code is None

    def test_with_error_code(self):
        inst = ErrorResponse(detail="Not found", error_code="NOT_FOUND")
        assert inst.detail == "Not found"
        assert inst.error_code == "NOT_FOUND"

    def test_empty_detail(self):
        """detail is required — empty string is acceptable as a value."""
        inst = ErrorResponse(detail="")
        assert inst.detail == ""

    def test_missing_detail_raises(self):
        with pytest.raises(ValidationError):
            ErrorResponse()  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ErrorResponse(detail="err", traceback="...")  # type: ignore[call-arg]

    def test_serialization_round_trip(self):
        original = ErrorResponse(detail="fail", error_code="ERR")
        dumped = original.model_dump()
        restored = ErrorResponse.model_validate(dumped)
        assert restored == original
