import logging
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from services.operations.alert_manager import AlertManager, Severity
from services.operations.event_bus import ALERT_CREATED, ALERT_RESOLVED, EventBus

logger = logging.getLogger("operations.notification_center")

SEVERITY_EMAIL_PREFIX = {
    Severity.CRITICAL: "[CRITICAL] ",
    Severity.WARNING: "[WARNING] ",
    Severity.INFO: "[INFO] ",
}


class NotificationCenter:
    def __init__(self, db=None, alert_recipients: Optional[list[str]] = None):
        self._db = db
        self._alert_mgr = AlertManager()
        self._event_bus = EventBus()
        self._subscribers: list[callable] = []
        self._subscribers_lock = threading.Lock()
        self._smtp_config: Optional[dict[str, Any]] = None
        self._alert_recipients: Optional[list[str]] = alert_recipients
        self._subscribe()

    def _subscribe(self):
        self._event_bus.subscribe(ALERT_CREATED, self._on_alert_created)
        self._event_bus.subscribe(ALERT_RESOLVED, self._on_alert_resolved)
        logger.info("NotificationCenter subscribed to events")

    def shutdown(self):
        try:
            self._event_bus.unsubscribe(ALERT_CREATED, self._on_alert_created)
            self._event_bus.unsubscribe(ALERT_RESOLVED, self._on_alert_resolved)
            logger.debug("NotificationCenter unsubscribed events")
        except Exception:
            pass

    def _on_alert_created(self, ev: dict[str, Any]) -> None:
        alert_data = ev["data"].get("alert", {})
        self._notify_all("alert_created", alert_data)

    def _on_alert_resolved(self, ev: dict[str, Any]) -> None:
        alert_data = ev["data"].get("alert", {})
        self._notify_all("alert_resolved", alert_data)

    def _notify_all(self, event_type: str, alert_data: dict[str, Any]) -> None:
        with self._subscribers_lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                cb(event_type, alert_data)
            except Exception as e:
                logger.error("Notification subscriber error: %s", e)

        severity_str = alert_data.get("severity", "info")
        if severity_str == "critical":
            threading.Thread(target=self._send_email_alert, args=(alert_data,), daemon=True).start()

    def subscribe(self, callback: callable) -> None:
        with self._subscribers_lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: callable) -> None:
        with self._subscribers_lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def configure_smtp(self, server: str, port: int, user: str, password: str, use_tls: bool = True) -> None:
        self._smtp_config = {
            "server": server,
            "port": port,
            "user": user,
            "password": password,
            "use_tls": use_tls,
        }
        logger.info("SMTP configured: %s:%d", server, port)

    def _send_email_alert(self, alert_data: dict[str, Any]) -> bool:
        if not self._smtp_config:
            logger.debug("SMTP not configured, skipping email alert")
            return False

        cfg = self._smtp_config
        try:
            msg = MIMEMultipart("alternative")
            title = alert_data.get("title", "Alert") or "Alert"
            safe_title = title.replace("\r", "").replace("\n", " ")
            msg["Subject"] = f"{SEVERITY_EMAIL_PREFIX.get(alert_data.get('severity', ''), '')}{safe_title}"
            msg["From"] = cfg["user"]

            recipients = self._get_alert_recipients(alert_data)
            if not recipients:
                logger.debug("No recipients for alert, skipping email")
                return False

            msg["To"] = ", ".join(recipients)

            body = (
                f"Alert: {alert_data.get('title', 'N/A')}\n"
                f"Severity: {alert_data.get('severity', 'N/A')}\n"
                f"Type: {alert_data.get('type', 'N/A')}\n"
                f"Message: {alert_data.get('message', 'N/A')}\n"
            )
            if alert_data.get("truck_id"):
                body += f"Truck: {alert_data['truck_id']}\n"
            if alert_data.get("trip_id"):
                body += f"Trip: {alert_data['trip_id']}\n"
            body += f"Time: {alert_data.get('created_at', 'N/A')}\n"

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as s:
                if cfg.get("use_tls", True):
                    s.starttls()
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["user"], recipients, msg.as_string())

            logger.info("Email alert sent to %s: %s", recipients, alert_data.get("title"))
            return True
        except smtplib.SMTPException as e:
            logger.error("SMTP error sending alert email: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to send alert email: %s", e)
            return False

    def _get_alert_recipients(self, alert_data: dict[str, Any]) -> list[str]:
        if self._alert_recipients:
            return self._alert_recipients
        if not self._db:
            return []
        try:
            cfg = self._db.get_settings(["alert_email_recipients"])
            raw = cfg.get("alert_email_recipients", "")
            return [e.strip() for e in raw.split(",") if e.strip()]
        except Exception:
            pass
        return []

    def send_test_email(self, recipient: str) -> bool:
        if not self._smtp_config:
            logger.warning("SMTP not configured, cannot send test")
            return False
        alert_data = {
            "title": "Test Notification",
            "severity": Severity.INFO.value,
            "type": "test",
            "message": "This is a test notification from the Operations Engine.",
            "created_at": __import__("datetime").datetime.now().isoformat(),
        }
        cfg = self._smtp_config
        try:
            msg = MIMEText(alert_data["message"])
            msg["Subject"] = alert_data["title"]
            msg["From"] = cfg["user"]
            msg["To"] = recipient
            with smtplib.SMTP(cfg["server"], cfg["port"], timeout=10) as s:
                if cfg.get("use_tls", True):
                    s.starttls()
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["user"], [recipient], msg.as_string())
            logger.info("Test email sent to %s", recipient)
            return True
        except Exception as e:
            logger.error("Test email failed: %s", e)
            return False

    def send_email(self, to_address: str, subject: str, body: str,
                   attachments: Optional[list[str]] = None,
                   html: bool = False,
                   trip_id: Optional[int] = None) -> bool:
        if not self._smtp_config:
            logger.warning("SMTP not configured, cannot send email")
            return False
        cfg = self._smtp_config
        try:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = cfg["user"]
            msg["To"] = to_address

            subtype = "html" if html else "plain"
            msg.attach(MIMEText(body, subtype, "utf-8"))

            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        from email import encoders
                        from email.mime.base import MIMEBase
                        part = MIMEBase("application", "octet-stream")
                        with open(filepath, "rb") as f:
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename=\"{os.path.basename(filepath)}\""
                        )
                        msg.attach(part)

            with smtplib.SMTP(cfg["server"], cfg["port"], timeout=15) as s:
                if cfg.get("use_tls", True):
                    s.starttls()
                s.login(cfg["user"], cfg["password"])
                s.sendmail(cfg["user"], [to_address], msg.as_string())

            logger.info("Email sent to %s: %s", to_address, subject)
            if self._db:
                try:
                    from repositories.automail_repository import AutoMailRepository
                    AutoMailRepository(self._db).log_email(trip_id, to_address, subject, "sent")
                except Exception:
                    pass
            return True
        except smtplib.SMTPException as e:
            logger.error("SMTP error sending email to %s: %s", to_address, e)
            return False
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_address, e)
            return False
