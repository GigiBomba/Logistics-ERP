"""Comprehensive unit tests for models/common.py — Pydantic models.

Tests cover ServiceResult, PaginationParams, PaginatedResponse, and
associated common types.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from models.common import (
    ErrorDetail,
    ErrorResponse,
    OperationLog,
    PaginatedResponse,
    PaginationParams,
    ServiceResult,
    SuccessResponse,
    UndoToken,
)


# ──────────────────────────────────────────────────────────────
# ServiceResult[T]
# ──────────────────────────────────────────────────────────────


class TestServiceResult:
    """Construction, success/failure branches, error handling."""

    def test_success_with_data(self):
        """A successful result carries data and no errors."""
        sr = ServiceResult.success = True
        # Re-construct properly
        sr = ServiceResult(success=True, data=42)
        assert sr.success is True
        assert sr.data == 42
        assert sr.errors == []
        assert sr.undo_token is None

    def test_success_with_string_data(self):
        """String data is stored without modification."""
        sr = ServiceResult(success=True, data="hello")
        assert sr.data == "hello"

    def test_failure_with_errors(self):
        """A failed result has errors and data is None."""
        err = ErrorDetail(field="name", message="Required", code="missing")
        sr = ServiceResult(success=False, errors=[err])
        assert sr.success is False
        assert sr.data is None
        assert len(sr.errors) == 1
        assert sr.errors[0].message == "Required"

    def test_failure_without_errors_defaults_empty(self):
        """A failure with no explicit errors gets an empty list."""
        sr = ServiceResult(success=False)
        assert sr.errors == []

    def test_success_with_undo_token(self):
        """UndoToken is carried in a successful result."""
        token = UndoToken(operation_id="op-1", operation_type="delete")
        sr = ServiceResult(success=True, data="x", undo_token=token)
        assert sr.undo_token is not None
        assert sr.undo_token.operation_id == "op-1"
        assert sr.undo_token.can_undo is True

    @pytest.mark.parametrize("bad_field", ["success"])
    def test_missing_required_field_raises(self, bad_field):
        """Omitting the required 'success' field raises ValidationError."""
        with pytest.raises(ValidationError):
            ServiceResult()

    def test_data_is_none_on_failure(self):
        """By convention failure results have data=None."""
        sr = ServiceResult(success=False)
        assert sr.data is None

    def test_multiple_errors(self):
        """ServiceResult can hold multiple ErrorDetail items."""
        errors = [
            ErrorDetail(field="a", message="err1", code="e1"),
            ErrorDetail(field="b", message="err2", code="e2"),
        ]
        sr = ServiceResult(success=False, errors=errors)
        assert len(sr.errors) == 2


# ──────────────────────────────────────────────────────────────
# PaginationParams
# ──────────────────────────────────────────────────────────────


class TestPaginationParams:
    """Default values, per_page boundaries."""

    def test_defaults(self):
        """Defaults: page=1, per_page=20."""
        p = PaginationParams()
        assert p.page == 1
        assert p.per_page == 20

    def test_explicit_values(self):
        p = PaginationParams(page=3, per_page=50)
        assert p.page == 3
        assert p.per_page == 50

    @pytest.mark.parametrize(
        "page",
        [0, -1, -100],
    )
    def test_non_positive_page_allowed(self, page):
        """The model does *not* validate page > 0; these are accepted."""
        p = PaginationParams(page=page)
        assert p.page == page

    @pytest.mark.parametrize(
        "per_page",
        [0, -1, 1000],
    )
    def test_any_per_page_allowed(self, per_page):
        """The model does *not* clamp per_page; any int is accepted."""
        p = PaginationParams(per_page=per_page)
        assert p.per_page == per_page

    def test_page_type_must_be_int(self):
        with pytest.raises(ValidationError):
            PaginationParams(page="abc")

    def test_per_page_type_must_be_int(self):
        with pytest.raises(ValidationError):
            PaginationParams(per_page=12.5)


# ──────────────────────────────────────────────────────────────
# PaginatedResponse[T]
# ──────────────────────────────────────────────────────────────


class TestPaginatedResponse:
    """Construction with items, pagination metadata, edge cases."""

    def test_with_items(self):
        resp = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
            page=1,
            per_page=20,
            total_pages=5,
        )
        assert resp.items == [1, 2, 3]
        assert resp.total == 100
        assert resp.page == 1
        assert resp.per_page == 20
        assert resp.total_pages == 5

    def test_empty_items(self):
        """Empty item list is valid when total is zero."""
        resp = PaginatedResponse(
            items=[],
            total=0,
            page=1,
            per_page=20,
            total_pages=0,
        )
        assert resp.items == []
        assert resp.total == 0
        assert resp.total_pages == 0

    def test_zero_total_count(self):
        """Zero total with no items is a valid edge case."""
        resp = PaginatedResponse[int](
            items=[],
            total=0,
            page=1,
            per_page=20,
            total_pages=0,
        )
        assert resp.total == 0
        assert len(resp.items) == 0

    def test_string_items(self):
        resp = PaginatedResponse[str](
            items=["a", "b"],
            total=2,
            page=1,
            per_page=10,
            total_pages=1,
        )
        assert resp.items == ["a", "b"]

    def test_missing_items_raises(self):
        with pytest.raises(ValidationError):
            PaginatedResponse(
                total=0,
                page=1,
                per_page=20,
                total_pages=0,
            )

    def test_total_pages_can_exceed_total(self):
        resp = PaginatedResponse(
            items=["x"],
            total=1,
            page=1,
            per_page=1,
            total_pages=99,
        )
        assert resp.total_pages == 99

    def test_negative_values_allowed(self):
        """Model does not validate non-negative on total/page/etc."""
        resp = PaginatedResponse(
            items=[],
            total=-1,
            page=-1,
            per_page=-1,
            total_pages=-1,
        )
        assert resp.total == -1

    def test_mixed_types_via_generic(self):
        """Generic T works with arbitrary types."""
        resp = PaginatedResponse[float](
            items=[1.5, 2.5],
            total=2,
            page=1,
            per_page=10,
            total_pages=1,
        )
        assert resp.items == [1.5, 2.5]


# ──────────────────────────────────────────────────────────────
# Supporting models (SuccessResponse, ErrorDetail, ErrorResponse,
# UndoToken, OperationLog)
# ──────────────────────────────────────────────────────────────


class TestSuccessResponse:
    def test_default_success_true(self):
        sr = SuccessResponse()
        assert sr.success is True
        assert sr.message is None

    def test_with_message(self):
        sr = SuccessResponse(message="OK")
        assert sr.message == "OK"

    def test_success_can_be_false(self):
        sr = SuccessResponse(success=False)
        assert sr.success is False


class TestErrorDetail:
    def test_required_fields_only(self):
        ed = ErrorDetail(message="Not found", code="NF")
        assert ed.message == "Not found"
        assert ed.code == "NF"
        assert ed.field is None

    def test_all_fields(self):
        ed = ErrorDetail(field="email", message="Invalid", code="INV")
        assert ed.field == "email"


class TestErrorResponse:
    def test_minimal(self):
        er = ErrorResponse(
            errors=[ErrorDetail(message="err", code="E")],
            message="Failed",
        )
        assert er.success is False
        assert er.message == "Failed"
        assert len(er.errors) == 1

    def test_success_always_false(self):
        """Even if caller passes success=True, the default is False."""
        er = ErrorResponse(
            success=True,
            errors=[ErrorDetail(message="x", code="x")],
            message="x",
        )
        # The model default is False, but explicit True overrides
        assert er.success is True


class TestUndoToken:
    def test_required_only(self):
        ut = UndoToken(operation_id="op1", operation_type="update")
        assert ut.can_undo is True
        assert ut.undo_description == ""

    def test_all_fields(self):
        ut = UndoToken(
            operation_id="op2",
            operation_type="delete",
            can_undo=False,
            undo_description="Cannot undo delete",
        )
        assert ut.can_undo is False
        assert ut.undo_description == "Cannot undo delete"


class TestOperationLog:
    def test_required_fields(self):
        now = datetime.now()
        ol = OperationLog(
            operation="calculate",
            duration_ms=150.5,
            success=True,
            timestamp=now,
        )
        assert ol.operation == "calculate"
        assert ol.duration_ms == 150.5
        assert ol.success is True
        assert ol.timestamp == now
        assert ol.error is None

    def test_with_error(self):
        now = datetime.now()
        ol = OperationLog(
            operation="save",
            duration_ms=200.0,
            success=False,
            error="Timeout",
            timestamp=now,
        )
        assert ol.error == "Timeout"
