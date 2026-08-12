"""Email provider abstraction for the waitlist system.

Provider-agnostic: swap implementations by changing one dependency-injection
line — never call a provider SDK directly from business logic.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract email provider interface.

    All waitlist email-sending code depends on this interface,
    never on a concrete implementation. To swap providers
    (e.g. Resend → Postmark), create a new subclass and change
    ONE dependency-injection line — no endpoint changes needed.
    """

    @abstractmethod
    def send(self, to: str, template_id: str, variables: Dict[str, Any]) -> bool:
        """Send a single transactional email.

        Args:
            to: Recipient email address.
            template_id: Provider-specific template identifier.
            variables: Template substitution variables.

        Returns:
            True if the email was accepted for delivery.
        """
        ...


class LoggingEmailProvider(EmailProvider):
    """Non-sending provider — logs to console/logger for development/testing.

    Swap to ResendProvider (or Postmark/SendGrid) for production by
    changing the dependency-injection line. All business logic
    stays unchanged.
    """

    def send(self, to: str, template_id: str, variables: Dict[str, Any]) -> bool:
        logger.info(
            "Email [%s] → %s | vars=%s",
            template_id, to, variables,
        )
        # Simulate accepted
        return True


class ResendProvider(EmailProvider):
    """Resend.com transactional email provider.

    Requires the ``resend`` Python package:
        pip install resend

    Set ``RESEND_API_KEY`` in your environment.
    """

    def __init__(self, api_key: str = "") -> None:
        import os
        self._api_key = api_key or os.environ.get("RESEND_API_KEY", "")
        if not self._api_key:
            logger.warning("ResendProvider: RESEND_API_KEY not set — emails will NOT be sent.")

    def send(self, to: str, template_id: str, variables: Dict[str, Any]) -> bool:
        if not self._api_key:
            logger.error("ResendProvider: cannot send — no API key configured.")
            return False

        try:
            import resend
            resend.api_key = self._api_key
            subject = variables.get("subject", "")
            html = variables.get("html", "")
            if not html:
                html = f"<p>{variables.get('body', '')}</p>"
            resend.Emails.send({
                "from": "Operion <noreply@operionerp.xyz>",
                "to": [to],
                "subject": subject,
                "html": html,
                "tags": [{"name": "template_id", "value": template_id}],
            })
            logger.info("Resend: sent template=%s to %s", template_id, to)
            return True
        except ImportError:
            logger.error(
                "ResendProvider: 'resend' package not installed. "
                "Install with: pip install resend"
            )
            return False
        except Exception as exc:
            logger.error("ResendProvider: send failed for %s: %s", to, exc)
            return False


# ── Default provider ──────────────────────────────────────────────────
# get_email_provider() auto-selects: ResendProvider when RESEND_API_KEY
# is set (production), otherwise LoggingEmailProvider (dev/tests).
# Tests override via set_email_provider().
_email_provider: Optional[EmailProvider] = None
_auto_provider: Optional[EmailProvider] = None


def get_email_provider() -> EmailProvider:
    """Return the current email provider (injected, else auto-selected)."""
    global _auto_provider
    if _email_provider is not None:
        return _email_provider
    if _auto_provider is None:
        if os.environ.get("RESEND_API_KEY"):
            _auto_provider = ResendProvider()
        else:
            _auto_provider = LoggingEmailProvider()
    return _auto_provider


def set_email_provider(provider: Optional[EmailProvider]) -> None:
    """Inject a different provider (tests/DI). Pass None to reset to auto."""
    global _email_provider
    _email_provider = provider
