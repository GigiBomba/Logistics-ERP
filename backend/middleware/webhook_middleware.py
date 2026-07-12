"""Webhook body middleware — preserves the raw request body for HMAC verification.

FastAPI's default ``Request.body()`` is single-read; the middleware reads
the body once and caches it on ``request.state.webhook_raw_body`` so that
the webhook receiver can access it for signature verification without
consuming the stream.
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Path prefix that triggers body preservation.
# Only webhook POST requests are intercepted; all other paths pass through
# with zero overhead.
WEBHOOK_PREFIX = "/api/v1/webhooks/"


class WebhookBodyMiddleware(BaseHTTPMiddleware):
    """Read and cache the raw request body for webhook endpoints.

    The raw bytes are stored at ``request.state.webhook_raw_body`` so that
    downstream handlers (specifically :func:`verify_webhook_signature`)
    can access them for HMAC computation without re-reading the stream.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Only intercept POST requests to the webhook prefix.
        if request.method == "POST" and path.startswith(WEBHOOK_PREFIX):
            body = await request.body()
            # Restore the body so FastAPI's own parser can still read it
            # (e.g. for JSON validation).
            async def _receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = _receive
            request.state.webhook_raw_body = body

        return await call_next(request)
