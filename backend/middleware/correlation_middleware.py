"""Correlation ID middleware — injects X-Request-ID into every request context."""
import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Context variable for correlation ID — accessible anywhere in the request lifecycle
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Get the current request's correlation ID."""
    return correlation_id_var.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Injects or propagates X-Request-ID header."""

    async def dispatch(self, request: Request, call_next):
        # Accept incoming correlation ID or generate new one
        correlation_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Correlation-ID")
            or str(uuid.uuid4())
        )

        # Set in context for downstream use
        token = correlation_id_var.set(correlation_id)

        try:
            response = await call_next(request)
            # Echo back in response
            response.headers["X-Request-ID"] = correlation_id
            return response
        finally:
            correlation_id_var.reset(token)
