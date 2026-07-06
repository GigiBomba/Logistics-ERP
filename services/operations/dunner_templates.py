"""Invoice reminder email templates for the Dunner module.

Three proactive templates sent before/during/after the invoice due date
to prevent late payments through timely communication.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("operations.dunner_templates")

_SUBJECT_DAY_27 = "Upcoming Payment Notice: Invoice {invoice_number} / {company_name}"
_SUBJECT_DAY_30 = "Invoice Due Today: Invoice {invoice_number} / {company_name}"
_SUBJECT_DAY_33 = "Past Due Follow-Up: Invoice {invoice_number} / {company_name}"

_BODY_DAY_27 = """Dear Accounts Payable Team,

This is a brief, automated notification to remind you that invoice number {invoice_number} ({total_amount} {currency}) is scheduled for payment in 3 days, on {due_date}.

For your convenience, we have attached the original invoice and the signed CMR proof of delivery to this email.

Please let us know if you require any additional information or documentation to ensure the payment is processed smoothly on the due date.

Thank you for your continued partnership,

Best regards,
{company_name}

Generated via Operion ERP"""

_BODY_DAY_30 = """Dear Accounts Payable Team,

We would like to inform you that invoice number {invoice_number} in the amount of {total_amount} {currency} is due today, {due_date}.

Once the wire transfer is executed, please reply to this email with a copy of the payment receipt (remittance advice). This allows our accounting department to instantly clear the balance and mark the transaction as complete.

Thank you for your prompt attention to this invoice.

Sincerely,
{company_name}"""

_BODY_DAY_33 = """Dear Accounts Payable Team,

Our system indicates that we have not yet received the payment confirmation for invoice {invoice_number} ({total_amount} {currency}), which was due 3 days ago on {due_date}.

We understand that administrative delays happen. Could you please check with your finance department to confirm if this payment has been scheduled or processed?

If the payment was already sent, please forward the bank transaction receipt so we can update our records immediately. If there is an issue holding up the release of funds, please let us know so we can assist you.

Thank you for your time,

Best regards,
{company_name}"""


def render_template(template: str, context: dict[str, Any]) -> str:
    """Replace ``{key}`` tokens in *template* with values from *context*.

    Unknown tokens are left untouched (safe for partial overrides).
    """
    for key, value in context.items():
        template = template.replace(f"{{{key}}}", str(value) if value is not None else "")
    return template


def template_day_27(
    invoice_number: str,
    total_amount: str,
    currency: str,
    due_date: str,
    company_name: str,
) -> tuple[str, str]:
    """Return (subject, body) for the 3-days-before reminder.

    Sent on day -3 (3 days before the due date) as a proactive
    administrative check that the paperwork has been received and
    scheduled for processing.
    """
    context = {
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "currency": currency,
        "due_date": due_date,
        "company_name": company_name,
    }
    subject = render_template(_SUBJECT_DAY_27, context)
    body = render_template(_BODY_DAY_27, context)
    return subject, body


def template_day_30(
    invoice_number: str,
    total_amount: str,
    currency: str,
    due_date: str,
    company_name: str,
) -> tuple[str, str]:
    """Return (subject, body) for the due-date notice.

    Sent on day 0 (the exact due date) as a final confirmation
    request before late flags trigger.
    """
    context = {
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "currency": currency,
        "due_date": due_date,
        "company_name": company_name,
    }
    subject = render_template(_SUBJECT_DAY_30, context)
    body = render_template(_BODY_DAY_30, context)
    return subject, body


def template_day_33(
    invoice_number: str,
    total_amount: str,
    currency: str,
    due_date: str,
    company_name: str,
) -> tuple[str, str]:
    """Return (subject, body) for the 3-days-late follow-up.

    Sent on day +3 (3 days past due) as the first actual late
    notice, kept light and helpful.
    """
    context = {
        "invoice_number": invoice_number,
        "total_amount": total_amount,
        "currency": currency,
        "due_date": due_date,
        "company_name": company_name,
    }
    subject = render_template(_SUBJECT_DAY_33, context)
    body = render_template(_BODY_DAY_33, context)
    return subject, body
