"""Email provider abstraction for the waitlist system.

Provider-agnostic: swap implementations by changing one dependency-injection
line — never call a provider SDK directly from business logic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

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
            # Resend sends via their API — this call is non-blocking for the provider
            # but we still call it synchronously here (Celery task wrapper handles async).
            resend.Emails.send({
                "from": "Operion <noreply@operionerp.xyz>",
                "to": [to],
                "subject": "",  # template-driven
                "html": "",     # template-driven
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


# ── Default provider (swap via DI for production) ────────────────────

# Change this ONE line to swap providers:
#   email_provider = ResendProvider(api_key="re_...")
#   email_provider = LoggingEmailProvider()
_email_provider: EmailProvider = LoggingEmailProvider()


def get_email_provider() -> EmailProvider:
    """Return the current email provider instance.

    Replace the module-level default with dependency injection
    in production (e.g. FastAPI Depends or a config switch).
    """
    return _email_provider


def set_email_provider(provider: EmailProvider) -> None:
    """Inject a different provider (used in tests or DI setup)."""
    global _email_provider
    _email_provider = provider
