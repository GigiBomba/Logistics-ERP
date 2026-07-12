"""Tests for backend/schemas/client.py — ClientBase, ClientResponse."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from pydantic import ValidationError

from backend.schemas.client import ClientBase, ClientResponse


# ── ClientBase ────────────────────────────────────────────────────────────────


class TestClientBase:
    """name, email, phone all have defaults; address optional; extra="forbid"."""

    def test_defaults(self):
        inst = ClientBase()
        assert inst.name == ""
        assert inst.email == ""
        assert inst.phone == ""
        assert inst.address is None

    def test_all_fields(self):
        inst = ClientBase(name="Acme Corp", email="info@acme.com", phone="+123456789", address="123 Main St")
        assert inst.name == "Acme Corp"
        assert inst.email == "info@acme.com"
        assert inst.address == "123 Main St"

    def test_partial(self):
        inst = ClientBase(name="Client")
        assert inst.name == "Client"
        assert inst.email == ""

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ClientBase(name="x", unknown="y")  # type: ignore[call-arg]


# ── ClientResponse ────────────────────────────────────────────────────────────


class TestClientResponse:
    """Extends ClientBase. Adds id (required), is_active (default True), created_at (default "")."""

    def test_valid(self):
        inst = ClientResponse(id=1, name="Acme Corp", email="a@b.com", phone="123")
        assert inst.id == 1
        assert inst.is_active is True
        assert inst.created_at == ""
        assert inst.name == "Acme Corp"

    def test_all_fields(self):
        inst = ClientResponse(
            id=1, name="Acme", email="a@b.com", phone="123",
            address="Addr", is_active=False, created_at="2025-01-01T00:00:00Z",
        )
        assert inst.is_active is False
        assert inst.created_at == "2025-01-01T00:00:00Z"
        assert inst.address == "Addr"

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            ClientResponse(name="x", email="a@b.com", phone="123")  # type: ignore[call-arg]

    def test_extra_field_ignored(self):
        """extra="ignore" — unknown fields are silently dropped."""
        inst = ClientResponse(id=1, name="n", email="e", phone="p", unknown="x")  # type: ignore[call-arg]
        assert not hasattr(inst, "unknown")

    def test_serialization_round_trip(self):
        original = ClientResponse(id=1, name="Acme", email="a@b.com", phone="123", is_active=False)
        dumped = original.model_dump()
        restored = ClientResponse.model_validate(dumped)
        assert restored == original
