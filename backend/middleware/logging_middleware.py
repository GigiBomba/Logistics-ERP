import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .correlation_middleware import get_correlation_id

logger = logging.getLogger("api.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response: Response = await call_next(request)
        duration = time.time() - start
        correlation_id = get_correlation_id()
        logger.info(
            "%s %s %s %.3fms [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration * 1000,
            correlation_id,
        )
        return response
