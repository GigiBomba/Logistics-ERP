"""Custom exception hierarchy for Operion services."""
from __future__ import annotations



class OperionError(Exception):
    """Base exception for all Operion-specific errors."""
    pass


class ValidationError(OperionError):
    """Input validation failed."""
    pass


class NotFoundError(OperionError):
    """Requested resource not found."""
    pass


class PermissionDeniedError(OperionError):
    """User lacks permission for operation."""
    pass


class DispatchError(OperionError):
    """Dispatch operation failed."""
    pass


class TripError(OperionError):
    """Trip operation failed."""
    pass


class InvoiceError(OperionError):
    """Invoice operation failed."""
    pass


class DocumentError(OperionError):
    """Document operation failed."""
    pass


class OCRError(OperionError):
    """OCR processing failed."""
    pass


class ExportError(OperionError):
    """Export operation failed."""
    pass


class RouteError(OperionError):
    """Route calculation failed."""
    pass


class ExternalServiceError(OperionError):
    """External API call failed."""
    pass
