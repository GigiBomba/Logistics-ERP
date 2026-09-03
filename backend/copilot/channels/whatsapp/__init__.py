"""WhatsApp channel — provider-agnostic adapter package (§21 Ph.4 item 3).

Providers self-register via ``@register_whatsapp_provider`` and expose
:meth:`WhatsAppProvider.send_text` + :meth:`WhatsAppProvider.health`.  The
Co-Pilot tools call the registry, never a provider SDK directly.
"""

from backend.copilot.channels.whatsapp.base import WhatsAppProvider
from backend.copilot.channels.whatsapp.cloud_api import WhatsAppCloudApiProvider
from backend.copilot.channels.whatsapp.registry import (
    get_whatsapp_provider,
    list_whatsapp_providers,
    register_whatsapp_provider,
    validate_registry,
)

__all__ = [
    "WhatsAppProvider",
    "WhatsAppCloudApiProvider",
    "get_whatsapp_provider",
    "list_whatsapp_providers",
    "register_whatsapp_provider",
    "validate_registry",
]