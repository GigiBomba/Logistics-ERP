"""RFC 7807 Problem Details error handling for the Operion API."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    """Machine-readable error codes following RFC 7807 conventions."""

    # General
    INTERNAL_ERROR = "internal-error"
    NOT_FOUND = "not-found"
    VALIDATION_ERROR = "validation-error"
    RATE_LIMITED = "rate-limited"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    METHOD_NOT_ALLOWED = "method-not-allowed"
    NOT_IMPLEMENTED = "not-implemented"
    SERVICE_UNAVAILABLE = "service-unavailable"
    IDEMPOTENCY_CONFLICT = "idempotency-conflict"

    # Auth
    INVALID_CREDENTIALS = "auth/invalid-credentials"
    TOKEN_EXPIRED = "auth/token-expired"
    TOKEN_INVALID = "auth/token-invalid"
    ACCOUNT_LOCKED = "auth/account-locked"
    INSUFFICIENT_PERMISSIONS = "auth/insufficient-permissions"
    INVALID_API_KEY = "auth/invalid-api-key"
    API_KEY_EXPIRED = "auth/api-key-expired"
    API_KEY_REVOKED = "auth/api-key-revoked"

    # Resources
    CLIENT_NOT_FOUND = "resource/client-not-found"
    TRIP_NOT_FOUND = "resource/trip-not-found"
    VEHICLE_NOT_FOUND = "resource/vehicle-not-found"
    DRIVER_NOT_FOUND = "resource/driver-not-found"
    INVOICE_NOT_FOUND = "resource/invoice-not-found"
    DOCUMENT_NOT_FOUND = "resource/document-not-found"
    ROUTE_NOT_FOUND = "resource/route-not-found"
    USER_NOT_FOUND = "resource/user-not-found"

    # Business logic
    VEHICLE_UNAVAILABLE = "business/vehicle-unavailable"
    DRIVER_UNAVAILABLE = "business/driver-unavailable"
    DRIVER_HOURS_EXCEEDED = "business/driver-hours-exceeded"
    INVOICE_ALREADY_FINALIZED = "business/invoice-already-finalized"
    INVOICE_ALREADY_CANCELLED = "business/invoice-already-cancelled"
    TRIP_CONFLICT = "business/trip-conflict"
    ROUTE_INVALID = "business/route-invalid"
    OCR_CONFIDENCE_LOW = "business/ocr-confidence-low"
    DUPLICATE_RESOURCE = "business/duplicate-resource"

    # Invitations
    INVITATION_INVALID = "invitation/invalid"
    INVITATION_EXPIRED = "invitation/expired"
    INVITATION_ALREADY_ACCEPTED = "invitation/already-accepted"

    # External integration
    EXTERNAL_API_ERROR = "integration/external-api-error"
    EXTERNAL_API_TIMEOUT = "integration/external-api-timeout"
    EXTERNAL_API_RATE_LIMITED = "integration/external-api-rate-limited"
    WEBHOOK_SIGNATURE_INVALID = "integration/webhook-signature-invalid"
    WEBHOOK_UNKNOWN_EVENT = "integration/webhook-unknown-event"
    INTEGRATION_DISABLED = "integration/disabled"


@dataclass
class ProblemDetail:
    """RFC 7807 Problem Details response."""

    type: str = "about:blank"
    title: str = ""
    status: int = 500
    detail: str = ""
    instance: str = ""
    error_code: str = ""
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = {
            "type": (
                self.type
                or f"https://api.operionerp.xyz/errors/{self.error_code}"
                if self.error_code
                else "about:blank"
            ),
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }
        if self.instance:
            result["instance"] = self.instance
        if self.error_code:
            result["error_code"] = self.error_code
        if self.errors:
            result["errors"] = self.errors
        return result


# Map exceptions to error codes
EXCEPTION_TO_ERROR = {
    "ValidationError": (ErrorCode.VALIDATION_ERROR, 422),
    "NotFoundError": (ErrorCode.NOT_FOUND, 404),
    "PermissionDeniedError": (ErrorCode.FORBIDDEN, 403),
    "OperionError": (ErrorCode.INTERNAL_ERROR, 500),
    "TripError": (ErrorCode.INTERNAL_ERROR, 500),
    "InvoiceError": (ErrorCode.INTERNAL_ERROR, 500),
    "DocumentError": (ErrorCode.INTERNAL_ERROR, 500),
    "OCRError": (ErrorCode.INTERNAL_ERROR, 500),
    "ExportError": (ErrorCode.INTERNAL_ERROR, 500),
    "RouteError": (ErrorCode.INTERNAL_ERROR, 500),
    "ExternalServiceError": (ErrorCode.EXTERNAL_API_ERROR, 502),
    "DispatchError": (ErrorCode.INTERNAL_ERROR, 500),
}

HTTP_STATUS_TO_ERROR = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.DUPLICATE_RESOURCE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL_ERROR,
    502: ErrorCode.EXTERNAL_API_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


def get_error_code_for_exception(exc: Exception) -> tuple[ErrorCode, int]:
    """Map an exception to an error code and HTTP status."""
    exc_name = type(exc).__name__

    # Check direct class name mapping
    for class_name, (code, status) in EXCEPTION_TO_ERROR.items():
        if exc_name == class_name or exc_name.endswith(class_name):
            return code, status

    # Check if it's a known HTTP exception
    if hasattr(exc, "status_code"):
        status = exc.status_code
        error_code = HTTP_STATUS_TO_ERROR.get(status, ErrorCode.INTERNAL_ERROR)
        return error_code, status

    return ErrorCode.INTERNAL_ERROR, 500
