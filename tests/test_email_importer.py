"""Tests for EmailImporter service."""
from unittest.mock import MagicMock, call, patch, PropertyMock

import pytest

from services.email_importer import EmailImporter


@pytest.fixture
def mock_callback():
    return MagicMock()


@pytest.fixture
def importer(mock_callback):
    return EmailImporter(
        file_callback=mock_callback,
        host="imap.example.com",
        port=993,
        user="test@example.com",
        password="secret",
        interval_s=1,
        whitelist={"allowed@example.com"},
        delete_after=False,
    )


class TestInitAndConfig:
    def test_configure_updates_settings(self, importer):
        importer.configure(
            host="new.host.com", port=143, user="new@user.com",
            password="newpass", interval_s=30,
            whitelist={"a@b.com"}, delete_after=True,
        )
        assert importer._host == "new.host.com"
        assert importer._port == 143
        assert importer._user == "new@user.com"
        assert importer._password == "newpass"
        assert importer._interval == 30
        assert importer._whitelist == {"a@b.com"}
        assert importer._delete is True

    def test_is_running_returns_false_when_not_started(self, importer):
        assert importer.is_running() is False

    def test_start_does_nothing_when_not_configured(self, mock_callback):
        imp = EmailImporter(mock_callback)
        imp.start()
        assert imp.is_running() is False

    def test_start_and_stop(self, importer):
        importer.start()
        assert importer.is_running() is True
        importer.stop()
        assert importer.is_running() is False

    def test_start_idempotent(self, importer):
        importer.start()
        thread_id = id(importer._thread)
        importer.start()  # second call should no-op
        assert id(importer._thread) == thread_id
        importer.stop()


class TestPollLoop:
    @patch("imaplib.IMAP4_SSL")
    def test_check_mailbox_no_new_messages(self, mock_imap, importer):
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b""])

        importer._check_mailbox()

        mock_conn.login.assert_called_once_with("test@example.com", "secret")
        mock_conn.select.assert_called_once_with("INBOX")
        mock_conn.search.assert_called_once_with(None, "UNSEEN")
        mock_conn.logout.assert_called_once()

    @patch("imaplib.IMAP4_SSL")
    def test_check_mailbox_processes_messages(self, mock_imap, importer, mock_callback):
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1 2"])

        raw_email = (
            "From: allowed@example.com\r\n"
            "To: test@example.com\r\n"
            "Subject: Test\r\n"
            "Content-Type: multipart/mixed; boundary=\"boundary\"\r\n"
            "\r\n"
            "--boundary\r\n"
            "Content-Type: application/pdf; name=\"doc.pdf\"\r\n"
            "Content-Disposition: attachment; filename=\"doc.pdf\"\r\n"
            "Content-Transfer-Encoding: base64\r\n"
            "\r\n"
            "JVBERi0xLjcK\r\n"
            "--boundary--\r\n"
        ).encode("utf-8")

        mock_conn.fetch.return_value = ("OK", [(b"1", raw_email)])

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            importer._check_mailbox()

        assert mock_callback.called

    @patch("imaplib.IMAP4_SSL")
    def test_whitelist_filters_out_non_whitelisted(self, mock_imap, importer, mock_callback):
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b"1"])

        raw_email = (
            "From: unknown@evil.com\r\n"
            "Subject: Phishing\r\n"
            "Content-Type: text/plain\r\n"
            "\r\n"
            "body"
        ).encode("utf-8")
        mock_conn.fetch.return_value = ("OK", [(b"1", raw_email)])

        importer._check_mailbox()

        mock_callback.assert_not_called()

    @patch("imaplib.IMAP4_SSL")
    def test_connection_failure_logged(self, mock_imap, importer):
        mock_imap.side_effect = ConnectionError("Connection refused")

        importer._check_mailbox()  # should not raise

    def test_cleanup_temp_dir(self):
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["old.txt"]), \
             patch("os.path.isfile", return_value=True), \
             patch("os.path.getmtime", return_value=0), \
             patch("os.remove") as mock_rm:
            EmailImporter._cleanup_temp_dir()
            mock_rm.assert_called_once()


class TestMessageProcessing:
    def test_extract_sender_with_brackets(self, importer):
        msg = MagicMock()
        msg.get.return_value = "John Doe <john@example.com>"
        result = importer._extract_sender(msg)
        assert result == "john@example.com"

    def test_extract_sender_plain_email(self, importer):
        msg = MagicMock()
        msg.get.return_value = "john@example.com"
        result = importer._extract_sender(msg)
        assert result == "john@example.com"

    def test_extract_sender_none(self, importer):
        msg = MagicMock()
        msg.get.return_value = ""
        result = importer._extract_sender(msg)
        assert result is None

    def test_save_attachments_skips_unsupported(self, importer):
        msg = MagicMock()
        part = MagicMock()
        part.get_content_maintype.return_value = "text"
        part.get_filename.return_value = "notes.txt"
        msg.walk.return_value = [part]

        paths = importer._save_attachments(msg)
        assert paths == []

    def test_save_attachments_saves_pdf(self, importer):
        msg = MagicMock()
        part = MagicMock()
        part.get_content_maintype.return_value = "application"
        part.get_filename.return_value = "doc.pdf"
        part.get_payload.return_value = b"pdf content"
        msg.walk.return_value = [part]

        with patch("os.makedirs"), \
             patch("builtins.open", MagicMock()):
            paths = importer._save_attachments(msg)
            assert len(paths) == 1
            assert paths[0].endswith(".pdf")


class TestIntegration:
    @patch("imaplib.IMAP4_SSL")
    def test_poll_loop_happy_path(self, mock_imap, importer, mock_callback):
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b""])

        # Make the poll loop exit after one iteration
        original_check = importer._check_mailbox
        def _run_once():
            original_check()
            importer._stop_event.set()
        importer._check_mailbox = _run_once

        importer._poll_loop()

        assert mock_conn.login.called
        assert mock_conn.logout.called

    def test_stop_clears_thread(self, importer):
        importer.start()
        thread = importer._thread
        importer.stop()
        assert importer._thread is None


# ── Additional tests ───────────────────────────────────────────────

class TestAdditional:
    def test_configure_empty_whitelist_defaults_to_empty(self, mock_callback):
        imp = EmailImporter(mock_callback)
        assert imp._whitelist == set()

    @patch("imaplib.IMAP4_SSL")
    def test_process_message_skips_when_fetch_fails(self, mock_imap, importer):
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.fetch.return_value = ("BAD", None)
        # Should not raise
        importer._process_message(mock_conn, b"1")

    @patch("imaplib.IMAP4_SSL")
    def test_process_message_handles_non_tuple_data(self, mock_imap, importer, mock_callback):
        """If fetch returns raw bytes instead of a tuple, it should still work."""
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        raw_email = (
            "From: allowed@example.com\r\n"
            "Subject: Test\r\n"
            "Content-Type: application/pdf; name=\"doc.pdf\"\r\n"
            "Content-Disposition: attachment; filename=\"doc.pdf\"\r\n"
            "\r\n"
            "content"
        ).encode("utf-8")
        mock_conn.fetch.return_value = ("OK", [raw_email])

        with patch("os.makedirs"), patch("builtins.open", MagicMock()):
            importer._process_message(mock_conn, b"1")

        assert mock_callback.called

    @patch("imaplib.IMAP4_SSL")
    def test_check_mailbox_handles_no_unseen(self, mock_imap, importer):
        """When search returns no messages, nothing should be processed."""
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("OK", [b""])
        importer._check_mailbox()
        mock_conn.fetch.assert_not_called()

    @patch("imaplib.IMAP4_SSL")
    def test_check_mailbox_handles_search_error(self, mock_imap, importer):
        """If search fails, the method should not raise."""
        mock_conn = MagicMock()
        mock_imap.return_value = mock_conn
        mock_conn.search.return_value = ("NO", None)
        importer._check_mailbox()
        mock_conn.logout.assert_called_once()

    def test_extract_sender_with_display_name_no_brackets(self, importer):
        msg = MagicMock()
        msg.get.return_value = "=?UTF-8?B?Tm9yYmVydA==?= <norbert@example.com>"
        result = importer._extract_sender(msg)
        assert result == "norbert@example.com"

    def test_extract_sender_with_invalid_email(self, importer):
        msg = MagicMock()
        msg.get.return_value = "Not an email at all"
        result = importer._extract_sender(msg)
        assert result is None

    def test_save_attachments_skips_multipart(self, importer):
        """Multipart parts should be skipped when walking attachments."""
        msg = MagicMock()
        multipart_part = MagicMock()
        multipart_part.get_content_maintype.return_value = "multipart"
        msg.walk.return_value = [multipart_part]
        paths = importer._save_attachments(msg)
        assert paths == []

    def test_configure_with_none_whitelist(self, mock_callback):
        imp = EmailImporter(mock_callback, host="imap.test.com", user="u", password="p")
        imp.configure(whitelist=None)
        assert imp._whitelist == set()

    def test_configure_with_partial_update(self, importer):
        """configure sets specified fields and defaults for others."""
        importer.configure(host="new.host.com")
        assert importer._host == "new.host.com"
        # Other fields get defaulted (configure is a full update)
        assert importer._port == 993
        assert importer._user == ""  # default for configure is ""
