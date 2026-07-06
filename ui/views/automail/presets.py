"""Pre-built automation presets for AutoMail.

Each preset includes:
    - A name and description
    - Schedule entries (trigger_type, days_offset, is_active, sort_order)
    - A default template (subject, body_text, body_html)
"""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "Friendly": {
        "description": "Gentle reminders starting 5 days before due. Best for long-term partners.",
        "schedules": [
            {"name": "Friendly Warning",  "trigger_type": "days_before_due", "days_offset": 5, "is_active": 1, "sort_order": 0},
            {"name": "Due Date Reminder", "trigger_type": "on_due_date",     "days_offset": 0, "is_active": 1, "sort_order": 1},
            {"name": "Gentle Follow-Up",  "trigger_type": "days_after_due",  "days_offset": 7, "is_active": 1, "sort_order": 2},
        ],
        "template": {
            "name": "Friendly (Preset)",
            "subject": "Payment Reminder: Invoice {invoice_number} / {company_name}",
            "body_text": (
                "Dear {client_contact},\n\n"
                "This is a friendly reminder that invoice {invoice_number} "
                "({total_amount} {currency}) is due on {due_date}.\n\n"
                "Please let us know if you require any additional information "
                "or documentation. We are happy to help.\n\n"
                "Thank you for your continued partnership.\n\n"
                "Best regards,\n{company_name}"
            ),
            "body_html": (
                "<p>Dear {client_contact},</p>"
                "<p>This is a friendly reminder that invoice "
                "<strong>{invoice_number}</strong> ({total_amount} {currency}) "
                "is due on <strong>{due_date}</strong>.</p>"
                "<p>Please let us know if you require any additional information.</p>"
                "<p>Thank you for your continued partnership.</p>"
                "<p>Best regards,<br>{company_name}</p>"
            ),
        },
    },
    "Professional": {
        "description": "Standard 3-days-before, due date, and 3-days-after cadence.",
        "schedules": [
            {"name": "Day 27 Reminder",  "trigger_type": "days_before_due", "days_offset": 3, "is_active": 1, "sort_order": 0},
            {"name": "Due Date Notice",  "trigger_type": "on_due_date",     "days_offset": 0, "is_active": 1, "sort_order": 1},
            {"name": "Day 33 Follow-Up", "trigger_type": "days_after_due",  "days_offset": 3, "is_active": 1, "sort_order": 2},
        ],
        "template": {
            "name": "Professional (Preset)",
            "subject": "Invoice {invoice_number} — Payment Reminder / {company_name}",
            "body_text": (
                "Dear Accounts Payable Team,\n\n"
                "This is a notification regarding invoice {invoice_number} "
                "({total_amount} {currency}), due on {due_date}.\n\n"
                "Kindly ensure the payment is processed by the due date. "
                "Please find the relevant documents attached.\n\n"
                "Sincerely,\n{company_name}"
            ),
            "body_html": (
                "<p>Dear Accounts Payable Team,</p>"
                "<p>This is a notification regarding invoice "
                "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                "due on <strong>{due_date}</strong>.</p>"
                "<p>Kindly ensure the payment is processed by the due date. "
                "Please find the relevant documents attached.</p>"
                "<p>Sincerely,<br>{company_name}</p>"
            ),
        },
    },
    "Strict": {
        "description": "Aggressive cadence starting at due date. For overdue accounts.",
        "schedules": [
            {"name": "Due Date Notice",  "trigger_type": "on_due_date",     "days_offset": 0,  "is_active": 1, "sort_order": 0},
            {"name": "Day 1 Follow-Up",  "trigger_type": "days_after_due",  "days_offset": 1,  "is_active": 1, "sort_order": 1},
            {"name": "Day 5 Follow-Up",  "trigger_type": "days_after_due",  "days_offset": 5,  "is_active": 1, "sort_order": 2},
            {"name": "Day 15 Final",     "trigger_type": "days_after_due",  "days_offset": 15, "is_active": 1, "sort_order": 3},
        ],
        "template": {
            "name": "Strict (Preset)",
            "subject": "URGENT: Invoice {invoice_number} / {company_name}",
            "body_text": (
                "Dear Accounts Payable Team,\n\n"
                "This is an urgent reminder for invoice {invoice_number} "
                "({total_amount} {currency}), due on {due_date}.\n\n"
                "We must insist on prompt payment to avoid any disruption of services. "
                "Please confirm the transfer date at your earliest convenience.\n\n"
                "Regards,\n{company_name}"
            ),
            "body_html": (
                "<p>Dear Accounts Payable Team,</p>"
                "<p>This is an urgent reminder for invoice "
                "<strong>{invoice_number}</strong> ({total_amount} {currency}), "
                "due on <strong>{due_date}</strong>.</p>"
                "<p>We must insist on prompt payment to avoid any disruption of "
                "services. Please confirm the transfer date at your earliest "
                "convenience.</p>"
                "<p>Regards,<br>{company_name}</p>"
            ),
        },
    },
}


def get_preset_names() -> list[str]:
    return list(PRESETS.keys())


def get_preset(name: str) -> dict[str, Any]:
    return PRESETS.get(name, {})
