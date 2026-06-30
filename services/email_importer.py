"""Email attachment importer — polls an IMAP mailbox for document
attachments and feeds them into the automation pipeline.

Designed for WhatsApp Business emails, customer-submitted documents,
and any other email sources.  Runs as a configurable-interval thread
that checks for unseen messages from whitelisted senders, downloads
image/PDF attachments, and invokes a callback.

Settings (stored in the ``settings`` table):
    - email_importer_enabled    (1/0)
    - email_importer_host       IMAP server hostname
    - email_importer_port       IMAP port (default 993)
    - email_importer_user       IMAP username
    - email_importer_password   IMAP password
    - email_importer_interval   Polling interval in seconds (default 60)
    - email_importer_whitelist  Comma-separated sender emails to accept
    - email_importer_delete     Delete processed emails (1/0, default 0)
"""

from __future__ import annotations

import contextlib
import email
import logging
import os
import re
import threading
import time
from typing import Callable

from services.document_automation.image_processor import (
    _IMAGE_EXTENSIONS,
    _PDF_EXTENSIONS,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTS = _IMAGE_EXTENSIONS | _PDF_EXTENSIONS
_DEFAULT_INTERVAL = 60


class EmailImporter:
    """Poll an IMAP mailbox and invoke a callback for each attachment.

    Typical usage::

        def on_files(paths):
            for p in paths:
                process(p)

        importer = EmailImporter(on_files)
        importer.start()   # background thread
        ...
        importer.stop()
    """

    def __init__(
        self,
        file_callback: Callable[[list[str]], None],
        host: str = "",
        port: int = 993,
        user: str = "",
        password: str = "",
        interval_s: int = _DEFAULT_INTERVAL,
        whitelist: set[str] | None = None,
        delete_after: bool = False,
    ) -> None:
        self._callback = file_callback
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._interval = interval_s
        self._whitelist = whitelist or set()
        self._delete = delete_after

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ── Public API ────────────────────────────────────────────────────

    def configure(
        self,
        host: str = "",
        port: int = 993,
        user: str = "",
        password: str = "",
        interval_s: int = _DEFAULT_INTERVAL,
        whitelist: set[str] | None = None,
        delete_after: bool = False,
    ) -> None:
        """Update configuration (applies on next poll cycle)."""
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._interval = interval_s
        self._whitelist = whitelist or set()
        self._delete = delete_after

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        if not self._host or not self._user or not self._password:
            logger.warning("EmailImporter: not configured, not starting")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="EmailImporter",
        )
        self._thread.start()
        logger.info(
            "EmailImporter started: %s@%s:%d interval=%ds whitelist=%d senders",
            self._user, self._host, self._port, self._interval, len(self._whitelist),
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("EmailImporter stopped")

    # ── Internal ──────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        _cleanup_counter = 0
        while not self._stop_event.is_set():
            try:
                self._check_mailbox()
                # Clean up old temp files every 10 cycles.
                _cleanup_counter += 1
                if _cleanup_counter >= 10:
                    _cleanup_counter = 0
                    self._cleanup_temp_dir()
            except Exception as exc:
                logger.warning("EmailImporter poll failed: %s", exc)
            self._stop_event.wait(self._interval)

    def _check_mailbox(self) -> None:
        import imaplib

        if not self._host or not self._user or not self._password:
            return

        try:
            conn = imaplib.IMAP4_SSL(self._host, self._port, timeout=30)
        except Exception as exc:
            logger.warning("EmailImporter: cannot connect to %s: %s", self._host, exc)
            return

        # Set a socket-level timeout so subsequent commands (login,
        # select, search, fetch) don't block indefinitely.
        with contextlib.suppress(Exception):
            conn.socket().settimeout(60)

        try:
            conn.login(self._user, self._password)
            conn.select("INBOX")

            # Search for unseen messages.
            status, data = conn.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return

            msg_ids = data[0].split()
            logger.debug("EmailImporter: %d unseen messages", len(msg_ids))

            for mid in msg_ids:
                if self._stop_event.is_set():
                    break
                self._process_message(conn, mid)
        except Exception as exc:
            logger.warning("EmailImporter: mailbox check failed: %s", exc)
        finally:
            with contextlib.suppress(Exception):
                conn.logout()

    def _process_message(self, conn, mid: bytes) -> None:

        status, data = conn.fetch(mid, "(RFC822)")
        if status != "OK":
            return

        raw_email = data[0][1] if isinstance(data[0], tuple) else data[0]
        if isinstance(raw_email, (bytes, bytearray)):
            raw_email = raw_email.decode("utf-8", errors="replace")

        msg = email.message_from_string(raw_email)

        # Check sender whitelist.
        sender = self._extract_sender(msg)
        if self._whitelist and sender and sender.lower() not in {s.lower() for s in self._whitelist}:
            logger.debug("EmailImporter: skipping %s (not in whitelist)", sender)
            return

        # Download attachments.
        paths = self._save_attachments(msg)
        if paths:
            logger.info("EmailImporter: imported %d attachment(s) from %s", len(paths), sender or "?")
            try:
                self._callback(paths)
            except Exception as exc:
                logger.warning("EmailImporter: callback failed for %d files: %s", len(paths), exc)
                # Do NOT return — files remain in inbox for retry on next poll
                return
            if self._delete:
                try:
                    conn.store(mid, "+FLAGS", "\\Deleted")
                    conn.expunge()
                except Exception as exc:
                    logger.warning("EmailImporter: failed to delete message: %s", exc)

    @staticmethod
    def _extract_sender(msg: email.message.Message) -> str | None:
        """Extract the sender email address from a message."""
        from_header = msg.get("From", "")
        # Match an email address: something@something.something
        m = re.search(r"<([^<>]+@[^<>]+)>", from_header)
        if m:
            return m.group(1).strip()
        m = re.search(r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})", from_header)
        if m:
            return m.group(1).strip()
        return None

    @staticmethod
    def _cleanup_temp_dir() -> None:
        """Remove temp files older than 7 days from the download dir."""
        temp_dir = os.path.join(__import__("tempfile").gettempdir(), "operion_email_imports")
        if not os.path.isdir(temp_dir):
            return
        cutoff = time.time() - 7 * 86400
        for fname in os.listdir(temp_dir):
            fpath = os.path.join(temp_dir, fname)
            try:
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
            except OSError:
                pass

    def _save_attachments(self, msg: email.message.Message) -> list[str]:
        """Download supported attachments to a temporary directory.

        Returns a list of saved file paths.
        """
        import tempfile

        paths: list[str] = []
        temp_dir = os.path.join(tempfile.gettempdir(), "operion_email_imports")
        os.makedirs(temp_dir, exist_ok=True)

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            filename = part.get_filename()
            if not filename:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in _SUPPORTED_EXTS:
                logger.debug("EmailImporter: skipping unsupported attachment: %s", filename)
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                continue

            # Avoid name collisions.
            safe_name = f"{int(time.time() * 1000)}_{len(paths)}_{os.path.basename(filename)}"
            dest = os.path.join(temp_dir, safe_name)
            try:
                with open(dest, "wb") as fh:
                    fh.write(payload)
                paths.append(dest)
            except OSError as exc:
                logger.warning("EmailImporter: failed to save %s: %s", filename, exc)

        return paths
