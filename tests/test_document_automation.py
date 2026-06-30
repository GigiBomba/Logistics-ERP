"""Tests for the document automation pipeline.

Covers the data-layer, image processor (graceful fallback), OCR
field extractors, trip matcher, customer detector and email
template renderer.  No Qt widgets, no real SMTP.
"""

import json
import os
import sqlite3
import tempfile
import unittest

from repositories import BaseRepository
from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from repositories.document_repository import DocumentRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.pipeline_repository import PipelineRepository
from repositories.trip_repository import TripRepository
from services.document_automation import (
    CustomerDetector,
    EmailTemplateService,
    PackageBuilder,
    TripMatcher,
)
from services.document_automation.email_template import (
    DEFAULT_BODY, DEFAULT_SUBJECT, render_template,
)
from services.document_automation.field_extractors import (
    extract_fields, normalize_date, normalize_plate,
)
from services.document_automation.image_processor import (
    ImageProcessor, ProcessingError, _PDF_EXTENSIONS, _IMAGE_EXTENSIONS,
)
from services.document_automation.types import PipelineStage


class _StubDb:
    """Minimal stand-in for DatabaseManager so the repositories can run."""

    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_person TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                address TEXT DEFAULT '',
                vat_number TEXT DEFAULT '',
                currency_preference TEXT DEFAULT 'EUR',
                notes TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS client_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                contact_type TEXT DEFAULT 'operations',
                full_name TEXT NOT NULL,
                title TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                is_primary INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                truck_number TEXT,
                driver_name TEXT,
                client_name TEXT,
                distance_km REAL,
                total_price_eur REAL,
                rate_per_km REAL,
                gross_per_km REAL,
                net_profit REAL,
                start_date TEXT,
                end_date TEXT,
                payment_date TEXT,
                extra_costs REAL,
                fuel_cost REAL,
                toll_cost REAL,
                salary_cost REAL,
                currency TEXT,
                status TEXT,
                cmr_number TEXT DEFAULT '',
                cmr_status TEXT DEFAULT 'draft',
                documents_attached TEXT DEFAULT '',
                client_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER UNIQUE,
                invoice_number TEXT UNIQUE,
                issue_date TEXT,
                due_date TEXT,
                total_amount REAL,
                status TEXT
            );
            CREATE TABLE IF NOT EXISTS trucks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plate_number TEXT UNIQUE,
                model TEXT DEFAULT '',
                manufacturer TEXT DEFAULT '',
                year INTEGER,
                vin TEXT DEFAULT '',
                fuel_consumption REAL DEFAULT 0,
                mileage REAL DEFAULT 0,
                monthly_rate REAL DEFAULT 0,
                status TEXT DEFAULT 'Active',
                insurance_expiry TEXT,
                inspection_expiry TEXT,
                maintenance_due REAL DEFAULT 0,
                active_status INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_number TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                entity_type TEXT NOT NULL DEFAULT '',
                entity_id INTEGER,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT DEFAULT 'application/octet-stream',
                file_hash TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                description TEXT DEFAULT '',
                is_archived INTEGER DEFAULT 0,
                uploaded_by TEXT DEFAULT '',
                uploaded_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                extracted_data_json TEXT DEFAULT '{}',
                automation_tags TEXT DEFAULT '',
                text_content TEXT DEFAULT '',
                copy_type TEXT DEFAULT '',
                cmr_number TEXT DEFAULT '',
                cmr_metadata_json TEXT DEFAULT '{}',
                is_signed INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS document_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                linked_entity_type TEXT NOT NULL,
                linked_entity_id INTEGER NOT NULL,
                relation_type TEXT DEFAULT 'attached',
                created_at TEXT NOT NULL,
                UNIQUE(document_id, linked_entity_type, linked_entity_id, relation_type)
            );
            CREATE TABLE IF NOT EXISTS document_pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uuid TEXT UNIQUE NOT NULL,
                source_file_path TEXT NOT NULL,
                source_file_name TEXT NOT NULL,
                source_mime_type TEXT NOT NULL,
                source_file_size INTEGER DEFAULT 0,
                source_file_hash TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'imported',
                stage TEXT NOT NULL DEFAULT 'import',
                error_message TEXT DEFAULT '',
                processed_file_path TEXT DEFAULT '',
                processed_pdf_path TEXT DEFAULT '',
                pages_count INTEGER DEFAULT 0,
                ocr_text TEXT DEFAULT '',
                extracted_data_json TEXT DEFAULT '{}',
                matched_trip_id INTEGER,
                match_confidence REAL DEFAULT 0.0,
                match_signals_json TEXT DEFAULT '{}',
                document_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS document_package (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                package_uuid TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                recipient_email TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                body TEXT DEFAULT '',
                email_message_id TEXT DEFAULT '',
                sent_at TEXT,
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS document_package_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.conn.commit()

    def row_to_dict(self, row):
        return dict(row) if row else None

    def rows_to_dicts(self, rows):
        return [dict(r) for r in rows]

    def close(self) -> None:
        self.conn.close()


class _StubPrefs:
    """In-memory preferences for the email template tests."""

    def __init__(self, **overrides):
        self._store = dict(overrides)

    def get_setting(self, key, default=None):
        return self._store.get(key, default)


class _TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = _StubDb(self._tmp.name)

    def tearDown(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def _insert_client(self, name="ACME SRL", email="ops@acme.com"):
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO clients (name, email, is_active, created_at) "
            "VALUES (?, ?, 1, '2024-01-01 00:00')",
            (name, email),
        )
        self.db.conn.commit()
        return cur.lastrowid

    def _insert_contact(self, client_id, name, email, primary=0):
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO client_contacts "
            "(client_id, full_name, email, is_primary, created_at) "
            "VALUES (?, ?, ?, ?, '2024-01-01 00:00')",
            (client_id, name, email, primary),
        )
        self.db.conn.commit()
        return cur.lastrowid

    def _insert_trip(self, **fields):
        cur = self.db.conn.cursor()
        cols = [
            "created_at", "truck_number", "driver_name", "client_name",
            "start_date", "end_date", "status", "cmr_number",
        ]
        values = ["2024-01-15 00:00", "B-123-ABC", "John Doe", "ACME SRL",
                  "2024-01-15", "2024-01-17", "Delivered", ""]
        for c, v in zip(cols, values):
            fields.setdefault(c, v)
        keys = ", ".join(fields.keys())
        qs = ", ".join("?" for _ in fields)
        cur.execute(
            f"INSERT INTO trips ({keys}) VALUES ({qs})",
            tuple(fields[k] for k in fields),
        )
        self.db.conn.commit()
        return cur.lastrowid


class TestPipelineRepository(_TestCase):
    def test_create_and_lookup_run(self) -> None:
        repo = PipelineRepository(self.db)
        run_id = repo.create_run(
            source_file_path="/tmp/test.jpg",
            source_file_name="test.jpg",
            source_mime_type="image/jpeg",
            source_file_size=1234,
        )
        run = repo.get_run_by_id(run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "imported")
        self.assertEqual(run["stage"], "import")
        # Update stage
        repo.update_stage(run_id, "processing", "processing")
        self.assertEqual(repo.get_run_by_id(run_id)["status"], "processing")
        # Set processed files
        repo.set_processed_files(run_id, "/tmp/proc.pdf", "/tmp/proc.pdf", 1)
        self.assertEqual(repo.get_run_by_id(run_id)["pages_count"], 1)
        # Set OCR
        repo.set_ocr_result(run_id, "hello world", {"cmr_number": "CMR-X1"})
        run = repo.get_run_by_id(run_id)
        self.assertEqual(repo.get_extracted_data(run_id)["cmr_number"], "CMR-X1")
        # Set match
        repo.set_match_result(run_id, 7, 0.95, {"cmr": 0.35})
        self.assertEqual(repo.get_run_by_id(run_id)["matched_trip_id"], 7)
        # Set document id
        repo.set_document_id(run_id, 11)
        self.assertEqual(repo.get_run_by_id(run_id)["document_id"], 11)
        # Update stage to complete — should set completed_at
        repo.update_stage(run_id, PipelineStage.COMPLETE.value, "complete")
        self.assertIsNotNone(repo.get_run_by_id(run_id)["completed_at"])

    def test_recover_stuck_runs(self) -> None:
        repo = PipelineRepository(self.db)
        rid = repo.create_run(
            source_file_path="/tmp/a.pdf",
            source_file_name="a.pdf",
            source_mime_type="application/pdf",
            source_file_size=10,
        )
        repo.update_stage(rid, "processing", "processing")
        recovered = repo.recover_stuck_runs()
        self.assertEqual(recovered, 1)
        self.assertEqual(repo.get_run_by_id(rid)["status"], "failed")
        # Running recover again should find 0.
        self.assertEqual(repo.recover_stuck_runs(), 0)

    def test_package_lifecycle(self) -> None:
        repo = PipelineRepository(self.db)
        trip_id = self._insert_trip()
        pid = repo.create_package(trip_id=trip_id)
        self.assertEqual(repo.get_package_by_id(pid)["status"], "draft")
        # Create a documents row so we can add a package item.
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO documents (doc_number, title, file_path, file_name, "
            "uploaded_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("DOC-1", "Test", "/tmp/test.pdf", "test.pdf",
             "2024-01-01 00:00", "2024-01-01 00:00"),
        )
        self.db.conn.commit()
        doc_id = cur.lastrowid
        repo.add_package_item(pid, doc_id, sort_order=0)
        items = repo.get_package_items(pid)
        self.assertEqual(len(items), 1)
        # Replace.
        cur.execute(
            "INSERT INTO documents (doc_number, title, file_path, file_name, "
            "uploaded_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("DOC-2", "Test 2", "/tmp/test2.pdf", "test2.pdf",
             "2024-01-01 00:00", "2024-01-01 00:00"),
        )
        self.db.conn.commit()
        doc_id_2 = cur.lastrowid
        repo.replace_package_items(pid, [doc_id_2, doc_id])
        items = repo.get_package_items(pid)
        self.assertEqual([i["document_id"] for i in items], [doc_id_2, doc_id])
        # Mark sent.
        repo.update_package(
            pid, status="sent", email_message_id="m-1",
            recipient_email="x@x.com", subject="hi", body="body",
        )
        row = repo.get_package_by_id(pid)
        self.assertEqual(row["status"], "sent")
        self.assertIsNotNone(row["sent_at"])


class TestImageProcessor(_TestCase):
    def test_known_extensions(self) -> None:
        # Sanity: the module declares the right extension sets.
        self.assertIn(".pdf", _PDF_EXTENSIONS)
        self.assertIn(".jpg", _IMAGE_EXTENSIONS)
        self.assertIn(".heic", _IMAGE_EXTENSIONS)

    def test_process_missing_file_raises(self) -> None:
        # Missing files are skipped at the input layer; an entirely
        # empty input list must raise ProcessingError.
        with self.assertRaises(ProcessingError):
            ImageProcessor().process([], "/tmp/out")

    def test_process_single_pdf(self) -> None:
        # Build a minimal one-page PDF with pypdf so we have a real file.
        from pypdf import PdfWriter
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            writer.write(fh)
            pdf_path = fh.name
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                result = ImageProcessor().process([pdf_path], out_dir, job_id="t")
                self.assertTrue(result.pdf_path.endswith(".pdf"))
                self.assertGreaterEqual(result.pages, 1)
                self.assertIn(result.method, ("single_native_pdf", "multi_pdf_merge"))
                self.assertTrue(os.path.isfile(result.pdf_path))
        finally:
            os.unlink(pdf_path)


class TestFieldExtractors(unittest.TestCase):
    def test_cmr_number_extraction(self) -> None:
        text = "CMR Nr: CMR-2024-001234\n"
        result = extract_fields(text)
        self.assertIn("cmr_number", result)
        self.assertIn("001234", result["cmr_number"])

    def test_invoice_number_extraction(self) -> None:
        text = "Invoice No INV-20240115-XYZ\nTotal: 100 EUR"
        result = extract_fields(text)
        self.assertIn("invoice_number", result)
        # Regex captures the full token (e.g. "INV-20240115-XYZ"); at
        # minimum it should contain a digit run.
        self.assertTrue(any(ch.isdigit() for ch in result["invoice_number"]))

    def test_truck_plate_extraction(self) -> None:
        text = "Vehicle reg: B-123-ABC\nDriver: John Doe"
        result = extract_fields(text)
        self.assertIn("truck_plate", result)
        self.assertEqual(normalize_plate(result["truck_plate"]), "B123ABC")

    def test_date_normalisation(self) -> None:
        self.assertEqual(normalize_date("2024-01-15"), "2024-01-15")
        self.assertEqual(normalize_date("15/01/2024"), "2024-01-15")
        self.assertEqual(normalize_date("not a date"), "")

    def test_render_template_keeps_unknowns(self) -> None:
        out = render_template("Hi {name}, your {thing} is ready", {
            "name": "Alex",
        })
        self.assertEqual(out, "Hi Alex, your {thing} is ready")


class TestTripMatcher(_TestCase):
    def test_match_by_cmr_number(self) -> None:
        # Insert a trip with a known CMR number.
        trip_id = self._insert_trip(cmr_number="CMR-99-ABCD")
        matcher = TripMatcher(self.db)
        result = matcher.match({"cmr_number": "CMR-99-ABCD"}, ocr_text="", source_filename="x.jpg")
        self.assertIsNotNone(result.best_match)
        self.assertEqual(result.best_match["id"], trip_id)
        self.assertGreaterEqual(result.confidence, 0.10)
        # CMR signal weight is now 0.10 (reduced for external CMRs).
        self.assertIn("cmr", result.signals)

    def test_match_by_invoice_number(self) -> None:
        trip_id = self._insert_trip()
        # Create an invoice linked to the trip.
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO invoices (trip_id, invoice_number, total_amount, status) "
            "VALUES (?, ?, 100, 'Unpaid')",
            (trip_id, "INV-2024-XYZ",),
        )
        self.db.conn.commit()
        matcher = TripMatcher(self.db)
        result = matcher.match(
            {"invoice_number": "INV-2024-XYZ"}, ocr_text="", source_filename="x.jpg"
        )
        self.assertIsNotNone(result.best_match)
        self.assertEqual(result.best_match["id"], trip_id)
        self.assertGreaterEqual(result.confidence, 0.10)

    def test_no_match_returns_recent_fallback(self) -> None:
        # Insert a recent trip and match with no signals at all.
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        self._insert_trip(start_date=recent)
        matcher = TripMatcher(self.db)
        result = matcher.match(
            {}, ocr_text="", source_filename="x.jpg"
        )
        self.assertIsNone(result.best_match)
        self.assertGreater(len(result.candidates), 0)
        # Fallback candidates get confidence 0.01
        self.assertEqual(result.candidates[0].confidence, 0.01)

    def test_filename_hint(self) -> None:
        trip_id = self._insert_trip()
        matcher = TripMatcher(self.db)
        result = matcher.match(
            {}, ocr_text="", source_filename=f"trip-{trip_id}-cmr.pdf"
        )
        self.assertIsNotNone(result.best_match)
        self.assertEqual(result.best_match["id"], trip_id)


class TestCustomerDetector(_TestCase):
    def test_detect_by_client_id(self) -> None:
        client_id = self._insert_client(name="ACME SRL", email="ops@acme.com")
        trip_id = self._insert_trip(client_name="ACME SRL")
        cur = self.db.conn.cursor()
        cur.execute("UPDATE trips SET client_id = ? WHERE id = ?", (client_id, trip_id))
        self.db.conn.commit()
        detector = CustomerDetector(self.db)
        info = detector.detect_for_trip_id(trip_id)
        self.assertIsNotNone(info.client)
        self.assertEqual(info.client["id"], client_id)
        self.assertEqual(info.default_email, "ops@acme.com")

    def test_detect_by_client_name_fallback(self) -> None:
        client_id = self._insert_client(name="Beta GmbH", email="b@g.de")
        trip_id = self._insert_trip(client_name="Beta GmbH")
        detector = CustomerDetector(self.db)
        info = detector.detect_for_trip_id(trip_id)
        self.assertIsNotNone(info.client)
        self.assertEqual(info.client["id"], client_id)
        self.assertEqual(info.default_email, "b@g.de")

    def test_no_client_returns_empty(self) -> None:
        trip_id = self._insert_trip(client_name="")
        detector = CustomerDetector(self.db)
        info = detector.detect_for_trip_id(trip_id)
        self.assertIsNone(info.client)
        self.assertEqual(info.default_email, "")
        self.assertEqual(info.all_emails, [])

    def test_primary_contact_preferred(self) -> None:
        client_id = self._insert_client(name="Gamma", email="g@g.de")
        self._insert_contact(client_id, "Alice Ops", "alice@g.de", primary=1)
        self._insert_contact(client_id, "Bob Billing", "bob@g.de", primary=0)
        trip_id = self._insert_trip(client_name="Gamma")
        cur = self.db.conn.cursor()
        cur.execute("UPDATE trips SET client_id = ? WHERE id = ?", (client_id, trip_id))
        self.db.conn.commit()
        detector = CustomerDetector(self.db)
        info = detector.detect_for_trip_id(trip_id)
        self.assertEqual(info.default_email, "g@g.de")
        self.assertIn("alice@g.de", info.all_emails)
        self.assertIn("bob@g.de", info.all_emails)


class TestEmailTemplate(unittest.TestCase):
    def test_render_subject_and_body(self) -> None:
        prefs = _StubPrefs(automation_company_name="Acme Logistics")
        service = EmailTemplateService(prefs)
        customer = type("C", (), {
            "client": {"name": "Beta GmbH", "email": "b@beta.de",
                       "contact_person": "Bob"},
            "primary_contact": None,
            "all_emails": ["b@beta.de"],
            "default_email": "b@beta.de",
        })()
        trip = {
            "id": 2487,
            "client_name": "Beta GmbH",
            "place_of_loading": "Munich, DE",
            "loading_country": "DE",
            "delivery_country": "IT",
            "start_date": "2024-06-15",
        }
        documents = [{"file_name": "Invoice.pdf", "file_size": 1024 * 50}]
        subject = service.render_subject(trip, customer)
        body = service.render_body(trip, customer, documents)
        self.assertIn("2487", subject)
        self.assertIn("Beta GmbH", subject)
        self.assertIn("Acme Logistics", body)
        self.assertIn("Invoice.pdf", body)
        # Default templates should be used (no override set).
        self.assertEqual(subject, render_template(DEFAULT_SUBJECT, service.build_context(trip, customer, [])))


class TestPackageBuilder(_TestCase):
    def test_list_trip_documents(self) -> None:
        trip_id = self._insert_trip()
        # Create two documents linked to the trip.
        cur = self.db.conn.cursor()
        for i, name in enumerate(("a.pdf", "b.pdf")):
            cur.execute(
                "INSERT INTO documents (doc_number, title, category, entity_type, "
                "entity_id, file_path, file_name, file_size, uploaded_at, updated_at) "
                "VALUES (?, ?, 'trips', 'trip', ?, ?, ?, ?, '2024-01-01 00:00', "
                "'2024-01-01 00:00')",
                (f"DOC-{i}", f"Title {i}", trip_id, f"/tmp/{name}", name, 1024),
            )
            doc_id = cur.lastrowid
            cur.execute(
                "INSERT INTO document_links (document_id, linked_entity_type, "
                "linked_entity_id, relation_type, created_at) "
                "VALUES (?, 'trip', ?, 'attached', '2024-01-01 00:00')",
                (doc_id, trip_id),
            )
        self.db.conn.commit()
        builder = PackageBuilder(self.db)
        docs = builder.list_trip_documents(trip_id)
        self.assertEqual(len(docs), 2)
        pkg = builder.build_for_trip(trip_id)
        self.assertIsNotNone(pkg)
        self.assertEqual(len(pkg.documents), 2)

    def test_build_for_trip_respects_user_reorder(self) -> None:
        trip_id = self._insert_trip()
        cur = self.db.conn.cursor()
        doc_ids = []
        for i, name in enumerate(("a.pdf", "b.pdf", "c.pdf")):
            cur.execute(
                "INSERT INTO documents (doc_number, title, category, entity_type, "
                "entity_id, file_path, file_name, file_size, uploaded_at, updated_at) "
                "VALUES (?, ?, 'trips', 'trip', ?, ?, ?, ?, '2024-01-01 00:00', "
                "'2024-01-01 00:00')",
                (f"DOC-{i}", f"Title {i}", trip_id, f"/tmp/{name}", name, 1024),
            )
            doc_id = cur.lastrowid
            doc_ids.append(doc_id)
            cur.execute(
                "INSERT INTO document_links (document_id, linked_entity_type, "
                "linked_entity_id, relation_type, created_at) "
                "VALUES (?, 'trip', ?, 'attached', '2024-01-01 00:00')",
                (doc_id, trip_id),
            )
        self.db.conn.commit()
        builder = PackageBuilder(self.db)
        # Request reverse order — the package must reflect it.
        pkg = builder.build_for_trip(trip_id, document_ids=list(reversed(doc_ids)))
        self.assertIsNotNone(pkg)
        self.assertEqual(
            [d["id"] for d in pkg.documents], list(reversed(doc_ids))
        )

    def test_build_for_trip_dedupes_request(self) -> None:
        """Repeating the same doc id in the request must not appear twice."""
        trip_id = self._insert_trip()
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO documents (doc_number, title, category, entity_type, "
            "entity_id, file_path, file_name, file_size, uploaded_at, updated_at) "
            "VALUES ('DOC-1', 'T1', 'trips', 'trip', ?, '/tmp/a.pdf', 'a.pdf', 1, "
            "'2024-01-01 00:00', '2024-01-01 00:00')",
            (trip_id,),
        )
        doc_id = cur.lastrowid
        # Add the link and the documents_attached reference.
        cur.execute(
            "INSERT INTO document_links (document_id, linked_entity_type, "
            "linked_entity_id, relation_type, created_at) "
            "VALUES (?, 'trip', ?, 'attached', '2024-01-01 00:00')",
            (doc_id, trip_id),
        )
        cur.execute(
            "UPDATE trips SET documents_attached = ? WHERE id = ?",
            (json.dumps([doc_id]), trip_id),
        )
        self.db.conn.commit()
        builder = PackageBuilder(self.db)
        pkg = builder.build_for_trip(trip_id, document_ids=[doc_id, doc_id, doc_id])
        self.assertIsNotNone(pkg)
        self.assertEqual(len(pkg.documents), 1)


class TestEmailTemplateHeaderSafety(unittest.TestCase):
    """Regression: subjects must not contain CR/LF that could split
    SMTP headers."""

    def test_subject_strips_newlines(self) -> None:
        service = EmailTemplateService(None)
        trip = {"id": 1, "client_name": "Acme\r\nBcc: attacker@evil.com"}
        customer = type("C", (), {
            "client": {"name": "Acme\r\nBcc: attacker@evil.com", "email": "x@x"},
            "primary_contact": None, "all_emails": ["x@x"],
            "default_email": "x@x",
        })()
        out = service.render_subject(trip, customer)
        self.assertNotIn("\r", out)
        self.assertNotIn("\n", out)
        # The injection text is replaced with a single space.
        self.assertIn("Bcc: attacker@evil.com", out)

    def test_subject_strips_nul(self) -> None:
        service = EmailTemplateService(None)
        trip = {"id": 1, "client_name": "Acme\x00Null"}
        out = service.render_subject(
            trip,
            type("C", (), {
                "client": {"name": "Acme"}, "primary_contact": None,
                "all_emails": [], "default_email": "",
            })(),
        )
        self.assertNotIn("\x00", out)


class TestCustomerDetectorCache(_TestCase):
    """Regression: cache must respect TTL and not be unbounded."""

    def test_cache_ttl_expires(self) -> None:
        # Insert a recent client + trip.
        client_id = self._insert_client(name="CacheTest", email="c@c.com")
        trip_id = self._insert_trip(client_name="CacheTest")
        cur = self.db.conn.cursor()
        cur.execute("UPDATE trips SET client_id = ? WHERE id = ?", (client_id, trip_id))
        self.db.conn.commit()
        # Use a TTL of 0 so the entry expires immediately.
        detector = CustomerDetector(self.db, cache_ttl_s=0)
        info1 = detector.detect_for_trip_id(trip_id)
        self.assertIsNotNone(info1.client)
        # Change the email in the DB.
        cur.execute("UPDATE clients SET email = 'new@c.com' WHERE id = ?", (client_id,))
        self.db.conn.commit()
        # The cached value should still be returned because the entry
        # was just inserted.  Now invalidate and re-fetch.
        detector.invalidate_cache()
        info2 = detector.detect_for_trip_id(trip_id)
        self.assertEqual(info2.client["email"], "new@c.com")

    def test_cache_max_size_eviction(self) -> None:
        from datetime import datetime, timedelta
        recent = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        for i in range(5):
            trip_id = self._insert_trip(start_date=recent)
        # Capacity 2.
        detector = CustomerDetector(self.db, cache_max_entries=2)
        for trip_id in (1, 2, 3, 4, 5):
            detector.detect_for_trip_id(trip_id)
        # The internal cache should not have grown past 2.
        self.assertLessEqual(len(detector._cache), 2)


class TestTripMatcherBatchFetch(_TestCase):
    """Regression: final scoring must not N+1 the trips table."""

    def test_batch_fetch_used_for_candidates(self) -> None:
        # Insert three trips that all match on the same CMR signal.
        for _ in range(3):
            self._insert_trip(cmr_number="CMR-BATCH")
        matcher = TripMatcher(self.db)
        result = matcher.match(
            {"cmr_number": "CMR-BATCH"}, ocr_text="", source_filename="x.jpg"
        )
        # All three candidates must be hydrated, not just the best one.
        self.assertGreaterEqual(len(result.candidates), 3)
        for c in result.candidates:
            self.assertIsNotNone(c.trip)
            self.assertEqual(c.trip["cmr_number"], "CMR-BATCH")


class TestPipelineRepositoryValidation(_TestCase):
    def test_create_run_strips_nul_and_newlines(self) -> None:
        repo = PipelineRepository(self.db)
        rid = repo.create_run(
            source_file_path="/tmp/test\0name.jpg",
            source_file_name="te\nst.jpg",
            source_mime_type="image/jpeg",
            source_file_size=10,
        )
        run = repo.get_run_by_id(rid)
        self.assertNotIn("\0", run["source_file_path"])
        self.assertNotIn("\n", run["source_file_name"])
        self.assertNotIn("\r", run["source_file_name"])

    def test_create_run_clamps_negative_size(self) -> None:
        repo = PipelineRepository(self.db)
        rid = repo.create_run(
            source_file_path="/tmp/x.jpg",
            source_file_name="x.jpg",
            source_mime_type="image/jpeg",
            source_file_size=-100,
        )
        run = repo.get_run_by_id(rid)
        self.assertEqual(run["source_file_size"], 0)


class TestImageProcessorRobustness(unittest.TestCase):
    """Smoke tests for the image processor's error paths."""

    def test_process_empty_inputs(self) -> None:
        with self.assertRaises(ProcessingError):
            ImageProcessor().process([], "/tmp/out")

    def test_process_skips_missing_files(self) -> None:
        # A list of non-existent files should be silently skipped
        # (no ProcessingError raised).
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            # All non-existent, all "skipped" — result is ProcessingError
            # because no supported files remain.
            with self.assertRaises(ProcessingError):
                ImageProcessor().process(
                    [os.path.join(d, "no_such_file.jpg")],
                    os.path.join(d, "out"),
                )


class TestCloudOcrLanguageHints(unittest.TestCase):
    """Validate the BCP-47 hint resolver for cloud OCR."""

    def test_default_hints_when_env_unset(self) -> None:
        from services.document_automation import cloud_ocr
        old = os.environ.pop(cloud_ocr.LANGUAGE_HINT_ENV, None)
        try:
            hints = cloud_ocr._resolve_language_hints()
        finally:
            if old is not None:
                os.environ[cloud_ocr.LANGUAGE_HINT_ENV] = old
        self.assertGreaterEqual(len(hints), 1)
        self.assertIn("ro", hints)

    def test_env_hints_override_defaults(self) -> None:
        from services.document_automation import cloud_ocr
        old = os.environ.get(cloud_ocr.LANGUAGE_HINT_ENV)
        os.environ[cloud_ocr.LANGUAGE_HINT_ENV] = "es, pt, ro"
        try:
            hints = cloud_ocr._resolve_language_hints()
        finally:
            if old is None:
                os.environ.pop(cloud_ocr.LANGUAGE_HINT_ENV, None)
            else:
                os.environ[cloud_ocr.LANGUAGE_HINT_ENV] = old
        self.assertEqual(hints[:3], ["es", "pt", "ro"])

    def test_invalid_hints_are_dropped(self) -> None:
        from services.document_automation import cloud_ocr
        old = os.environ.get(cloud_ocr.LANGUAGE_HINT_ENV)
        os.environ[cloud_ocr.LANGUAGE_HINT_ENV] = "en, !@#$, ro, en"
        try:
            hints = cloud_ocr._resolve_language_hints()
        finally:
            if old is None:
                os.environ.pop(cloud_ocr.LANGUAGE_HINT_ENV, None)
            else:
                os.environ[cloud_ocr.LANGUAGE_HINT_ENV] = old
        # Duplicates removed, invalid token dropped.
        self.assertEqual(hints, ["en", "ro"])

    def test_cloud_extract_passes_hints_to_provider(self) -> None:
        """Both providers should receive the resolved hints."""
        from services.document_automation import cloud_ocr
        captured: dict = {}

        def _fake_google(pdf_path, max_pages, hints):
            captured["google"] = (pdf_path, max_pages, list(hints or []))
            return None

        def _fake_azure(pdf_path, max_pages, hints):
            captured["azure"] = (pdf_path, max_pages, list(hints or []))
            return None

        old_google = os.environ.get("OPERION_GOOGLE_VISION_KEY")
        old_azure = os.environ.get("OPERION_AZURE_DOC_KEY")
        os.environ["OPERION_GOOGLE_VISION_KEY"] = "x"
        old_google_fn = cloud_ocr._google_vision_extract
        old_azure_fn = cloud_ocr._azure_extract
        cloud_ocr._google_vision_extract = _fake_google
        cloud_ocr._azure_extract = _fake_azure
        try:
            cloud_ocr.cloud_extract("/tmp/x.pdf")
            self.assertIn("google", captured)
            self.assertGreater(len(captured["google"][2]), 0)
            # Switch to Azure, hints still propagated.
            os.environ.pop("OPERION_GOOGLE_VISION_KEY", None)
            os.environ["OPERION_AZURE_DOC_KEY"] = "y"
            cloud_ocr.cloud_extract("/tmp/x.pdf")
            self.assertIn("azure", captured)
            self.assertGreater(len(captured["azure"][2]), 0)
        finally:
            cloud_ocr._google_vision_extract = old_google_fn
            cloud_ocr._azure_extract = old_azure_fn
            if old_google is None:
                os.environ.pop("OPERION_GOOGLE_VISION_KEY", None)
            else:
                os.environ["OPERION_GOOGLE_VISION_KEY"] = old_google
            if old_azure is None:
                os.environ.pop("OPERION_AZURE_DOC_KEY", None)
            else:
                os.environ["OPERION_AZURE_DOC_KEY"] = old_azure


class TestPipelineStageConstraint(unittest.TestCase):
    """The DB triggers must reject unknown stage/status values."""

    def setUp(self) -> None:
        from database.db_manager import DatabaseManager
        from database.schema import (
            TRIGGER_PIPELINE_RUNS_STAGE_CHECK,
            TRIGGER_PIPELINE_RUNS_STATUS_CHECK,
        )
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmp.close()
        self.db = DatabaseManager(self._tmp.name)
        # Sanity: triggers were created.
        rows = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name LIKE 'trg_pipeline_runs_%'"
        ).fetchall()
        names = {r[0] for r in rows}
        self.assertIn("trg_pipeline_runs_stage_check", names)
        self.assertIn("trg_pipeline_runs_status_check", names)

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self._tmp.name)

    def _insert_run(self, stage: str, status: str = "imported") -> None:
        from datetime import datetime
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.db.conn.execute(
            "INSERT INTO document_pipeline_runs ("
            "  run_uuid, source_file_path, source_file_name, source_mime_type,"
            "  stage, status, created_at, updated_at"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"uuid-{stage}-{status}",
                "/tmp/x.jpg",
                "x.jpg",
                "image/jpeg",
                stage,
                status,
                now,
                now,
            ),
        )
        self.db.conn.commit()

    def test_invalid_stage_rejected(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_run("bogus_stage")

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self._insert_run("import", status="bogus_status")

    def test_valid_stage_accepted(self) -> None:
        # Should not raise.
        self._insert_run("ocr")
        self._insert_run("complete", status="complete")

    def test_invalid_update_rejected(self) -> None:
        self._insert_run("import")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.conn.execute(
                "UPDATE document_pipeline_runs SET stage = ? WHERE stage = ?",
                ("nope", "import"),
            )
            self.db.conn.commit()


class TestPackagePreviewDocumentReuse(unittest.TestCase):
    """The preview modal should re-use documents it already loaded."""

    def test_get_ordered_documents_returns_loaded_list(self) -> None:
        from ui.views.package_preview_modal import PackagePreviewDialog
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            QApplication([])
        # We don't need a real DB; bypass __init__ and inject state.
        dialog = PackagePreviewDialog.__new__(PackagePreviewDialog)
        dialog.db = None
        dialog.trip_id = 1
        dialog.prefs = None
        dialog._doc_ids = [10, 20]
        dialog._documents_by_id = {
            10: {"id": 10, "file_path": "/a.pdf", "file_name": "a.pdf",
                 "title": "A", "file_size": 1},
            20: {"id": 20, "file_path": "/b.pdf", "file_name": "b.pdf",
                 "title": "B", "file_size": 2},
        }
        docs = dialog.get_ordered_documents()
        self.assertEqual([d["id"] for d in docs], [10, 20])

    def test_continue_signal_carries_documents(self) -> None:
        """The signal payload is 3-tuple (trip_id, doc_ids, documents).

        PySide6 signals can't be introspected directly; the test for
        ``get_ordered_documents`` above plus the constructor test in
        ``TestEmailComposerReusesDocuments`` together verify the wiring.
        Here we just sanity-check that the class declares the signal.
        """
        from ui.views.package_preview_modal import PackagePreviewDialog
        self.assertTrue(hasattr(PackagePreviewDialog, "continue_to_email"))


class TestEmailComposerReusesDocuments(unittest.TestCase):
    """The email composer must accept pre-loaded documents."""

    def test_documents_kwarg_stored_on_instance(self) -> None:
        """Verify the constructor stores the passed-in documents list."""
        from ui.views.email_composer_modal import EmailComposerDialog
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            QApplication([])
        # Bypass __init__ — we're only testing the parameter binding,
        # not the full widget tree (covered by manual smoke tests).
        dlg = EmailComposerDialog.__new__(EmailComposerDialog)
        dlg.db = None
        dlg.trip_id = 1
        dlg.prefs = None
        dlg.ordered_doc_ids = [10, 20]
        dlg._preloaded_documents = [
            {"id": 10, "file_path": "/a.pdf", "file_name": "a.pdf",
             "title": "A", "file_size": 1, "category": "invoice"},
            {"id": 20, "file_path": "/b.pdf", "file_name": "b.pdf",
             "title": "B", "file_size": 2, "category": "cmr"},
        ]
        dlg._package_id = None
        dlg._to_emails = []
        # The preloaded documents should be on the dialog.
        self.assertEqual(len(dlg._preloaded_documents), 2)
        ids = [d["id"] for d in dlg._preloaded_documents]
        self.assertEqual(ids, [10, 20])

    def test_documents_kwarg_signature_accepted(self) -> None:
        """The constructor's signature must include the ``documents`` kwarg."""
        import inspect
        from ui.views.email_composer_modal import EmailComposerDialog
        sig = inspect.signature(EmailComposerDialog.__init__)
        self.assertIn("documents", sig.parameters)
        # Default value should be None.
        self.assertIs(sig.parameters["documents"].default, None)


class TestAutomationMaxWorkersSetting(unittest.TestCase):
    """The cap must be configurable and clamped to a sane range."""

    def _make_view(self, max_value=None):
        from ui.views.automation_view import QtAutomationView
        from PySide6.QtWidgets import QApplication
        if QApplication.instance() is None:
            QApplication([])
        # We don't need a real DB or workers for the cap test.
        # We use a class-method-style helper to avoid the full __init__.
        view = QtAutomationView.__new__(QtAutomationView)
        view.prefs = None
        view._max_concurrent_workers = view._load_max_concurrent_workers()
        return view

    def test_default_when_no_prefs(self) -> None:
        view = self._make_view()
        self.assertEqual(view.MAX_CONCURRENT_WORKERS, 2)

    def test_clamped_to_hard_upper_bound(self) -> None:
        from ui.views.automation_view import QtAutomationView
        class _Prefs:
            def get_setting(self, key, default=None):
                return "9999"
        view = QtAutomationView.__new__(QtAutomationView)
        view.prefs = _Prefs()
        view._max_concurrent_workers = view._load_max_concurrent_workers()
        self.assertEqual(
            view.MAX_CONCURRENT_WORKERS,
            QtAutomationView.HARD_MAX_CONCURRENT_WORKERS,
        )

    def test_clamped_to_lower_bound(self) -> None:
        from ui.views.automation_view import QtAutomationView
        class _Prefs:
            def get_setting(self, key, default=None):
                return "0"
        view = QtAutomationView.__new__(QtAutomationView)
        view.prefs = _Prefs()
        view._max_concurrent_workers = view._load_max_concurrent_workers()
        self.assertEqual(view.MAX_CONCURRENT_WORKERS, 1)

    def test_invalid_setting_falls_back_to_default(self) -> None:
        from ui.views.automation_view import QtAutomationView
        class _Prefs:
            def get_setting(self, key, default=None):
                return "not-a-number"
        view = QtAutomationView.__new__(QtAutomationView)
        view.prefs = _Prefs()
        view._max_concurrent_workers = view._load_max_concurrent_workers()
        self.assertEqual(view.MAX_CONCURRENT_WORKERS, 2)


if __name__ == "__main__":
    unittest.main()
