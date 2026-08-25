"""Test data factory helpers for creating model instances with sensible defaults."""
from __future__ import annotations


from .factories import (
    make_trip,
    make_client,
    make_driver,
    make_user,
    make_vehicle,
    make_invoice,
)

__all__ = [
    "make_trip",
    "make_client",
    "make_driver",
    "make_user",
    "make_vehicle",
    "make_invoice",
]
