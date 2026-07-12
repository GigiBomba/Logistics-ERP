"""Custom exceptions for DispatchService."""

from __future__ import annotations


class DispatchError(Exception):
    """Base exception for all dispatch operations."""


class TripNotFoundError(DispatchError):
    """Trip does not exist in the database."""


class TruckNotFoundError(DispatchError):
    """Truck does not exist or is inactive."""


class DriverNotFoundError(DispatchError):
    """Driver does not exist or is inactive."""


class ResourceUnavailableError(DispatchError):
    """Truck/driver has a scheduling conflict or is blocked by compliance issues."""


class InvalidStatusTransitionError(DispatchError):
    """Requested status transition is not allowed."""


class TripArchivedError(DispatchError):
    """Operation rejected because trip is archived (read-only)."""
