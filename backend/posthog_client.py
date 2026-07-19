import atexit
import os
from typing import Optional

from posthog import Posthog

_client: Optional[Posthog] = None


def init_posthog(token: str, host: str) -> Posthog:
    global _client
    _client = Posthog(
        project_api_key=token,
        host=host,
        enable_exception_autocapture=True,
    )
    atexit.register(_client.shutdown)
    return _client


def get_posthog() -> Optional[Posthog]:
    return _client
