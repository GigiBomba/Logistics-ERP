"""Package builder — gather all trip-linked documents into a draft.

Reads every document currently linked to the trip (via
``document_links`` and via the trip's own ``documents_attached`` JSON
column) and creates a :class:`document_package` row that the email
composer can then act on.

Also supports:
    - ZIP file creation of all trip documents.
    - Combined PDF merging (inserts a cover page).
    - Cover page generation with trip summary.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from repositories.document_repository import DocumentRepository
from repositories.pipeline_repository import PipelineRepository
from repositories.trip_repository import TripRepository

logger = logging.getLogger("document_automation.package_builder")


@dataclass
class Package:
    """In-memory representation of a customer document package."""
    package_id: int
    trip_id: int | None
    package_uuid: str
    documents: list[dict[str, Any]] = field(default_factory=list)
    recipient_email: str = ""
    subject: str = ""
    body: str = ""


def _row_to_doc_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a documents row to the keys the email composer needs."""
    return {
        "id": row.get("id"),
        "doc_number": row.get("doc_number", ""),
        "title": row.get("title", ""),
        "file_path": row.get("file_path", ""),
        "file_name": row.get("file_name", ""),
        "file_size": row.get("file_size", 0) or 0,
        "mime_type": row.get("mime_type", ""),
        "category": row.get("category", ""),
        "cmr_number": row.get("cmr_number", ""),
        "is_signed": row.get("is_signed", 0) or 0,
    }


class PackageBuilder:
    """Stateless builder — safe to call from worker threads."""

    def __init__(self, db, docs_repo=None, trips_repo=None, pipeline_repo=None) -> None:
        self.db = db
        self.docs = docs_repo if docs_repo is not None else DocumentRepository(db)
        self.trips = trips_repo if trips_repo is not None else TripRepository(db)
        self.pipeline = pipeline_repo if pipeline_repo is not None else PipelineRepository(db)

    def list_trip_documents(self, trip_id: int) -> list[dict[str, Any]]:
        """Return all documents linked to the given trip, deduped and ordered.

        Sources:
            1. The ``documents`` table joined to ``document_links`` for
               this trip.
            2. The ``documents_attached`` JSON column on the trip
               (used by the existing CMR auto-generator).
        """
        seen: dict[int, dict[str, Any]] = {}
        for row in self.docs.get_documents_for_entity("trip", trip_id):
            doc_id = row.get("id")
            if doc_id is None:
                continue
            seen[int(doc_id)] = _row_to_doc_summary(row)
        # Pick up docs referenced only from the JSON column.
        trip = self.trips.get_by_id(trip_id)
        if trip and trip.get("documents_attached"):
            try:
                ids = json.loads(trip["documents_attached"])
            except (ValueError, TypeError):
                ids = []
            if isinstance(ids, list):
                missing = []
                for raw in ids:
                    try:
                        did = int(raw)
                    except (TypeError, ValueError):
                        continue
                    if did not in seen:
                        missing.append(did)
                # Batch-fetch missing docs in a single query.
                if missing:
                    for r in self.docs.get_by_ids_batch(missing):
                        doc_id = r["id"]
                        seen[int(doc_id)] = _row_to_doc_summary(dict(r))
        # Sort: signed CMRs first, then invoices, then by title.
        def _sort_key(d: dict[str, Any]) -> tuple:
            signed = 0 if d.get("is_signed") else 1
            invoice = 0 if (d.get("category") or "") == "invoices" else 1
            return (signed, invoice, (d.get("title") or "").lower(), d.get("id", 0))
        return sorted(seen.values(), key=_sort_key)

    def build_for_trip(
        self,
        trip_id: int,
        document_ids: list[int] | None = None,
    ) -> Package | None:
        """Create a draft package for ``trip_id`` and return the Package.

        ``document_ids`` lets the caller supply the user's reorder
        decision.  When omitted, the natural sort order is used.
        """
        documents = self.list_trip_documents(trip_id)
        if not documents:
            logger.info("build_for_trip: no documents linked to trip %s", trip_id)
            return None

        if document_ids is not None:
            # Reorder the documents list to match the user's order.
            # Dedupe the requested IDs (preserving first occurrence) and
            # fall back to the natural order for any document that was
            # not in the requested list (e.g. a new doc linked between
            # the package preview and the email composer).
            requested: list[int] = []
            seen_in_request: set = set()
            for raw in document_ids:
                try:
                    did = int(raw)
                except (TypeError, ValueError):
                    continue
                if did in seen_in_request:
                    continue
                seen_in_request.add(did)
                requested.append(did)
            by_id = {int(d.get("id", -1)): d for d in documents if d.get("id") is not None}
            ordered: list[dict[str, Any]] = []
            for did in requested:
                if did in by_id:
                    ordered.append(by_id[did])
                    del by_id[did]
            # Append any remaining documents in their natural order.
            ordered.extend(by_id.values())
            documents = ordered

        package_id = self.pipeline.create_package(trip_id=trip_id)
        doc_ids = []
        for doc in documents:
            try:
                doc_ids.append(int(doc["id"]))
            except (TypeError, ValueError):
                logger.warning("build_for_trip: skipping doc with invalid id: %s", doc.get("id"))
        if doc_ids:
            try:
                self.pipeline.replace_package_items(package_id, doc_ids)
            except Exception:
                logger.exception("Failed to replace package items for package %d", package_id)
                raise
        row = self.pipeline.get_package_by_id(package_id)
        if not row:
            return None
        return Package(
            package_id=row["id"],
            trip_id=row["trip_id"],
            package_uuid=row["package_uuid"],
            documents=documents,
        )

    def build_standalone(
        self,
        documents: list[dict[str, Any]],
    ) -> Package | None:
        """Create a draft package with no trip association (standalone).

        Used by Simple mode in the Automation tab when the user chooses
        not to associate the processed document(s) with any trip.

        ``documents`` must be a list of document dicts (as returned by
        e.g. ``DocumentRepository``) that should be packaged together.
        """
        if not documents:
            logger.info("build_standalone: no documents provided")
            return None

        package_id = self.pipeline.create_package(trip_id=None)
        doc_ids = []
        for doc in documents:
            try:
                doc_ids.append(int(doc["id"]))
            except (TypeError, ValueError):
                logger.warning(
                    "build_standalone: skipping doc with invalid id: %s",
                    doc.get("id"),
                )
        if doc_ids:
            try:
                self.pipeline.replace_package_items(package_id, doc_ids)
            except Exception:
                logger.exception(
                    "Failed to replace package items for package %d",
                    package_id,
                )
                raise
        row = self.pipeline.get_package_by_id(package_id)
        if not row:
            return None
        return Package(
            package_id=row["id"],
            trip_id=None,
            package_uuid=row["package_uuid"],
            documents=documents,
        )

    # ── ZIP packaging ────────────────────────────────────────────────

    def build_zip(self, trip_id: int, output_dir: str) -> str | None:
        """Create a ZIP archive of all documents linked to *trip_id*.

        Returns the path to the ZIP file, or ``None`` if no documents.
        """
        import shutil
        import tempfile

        docs = self.list_trip_documents(trip_id)
        if not docs:
            return None

        temp_dir = tempfile.mkdtemp(prefix="pkg_")
        zip_name = f"trip_{trip_id}_{datetime.now().strftime('%Y%m%d')}.zip"
        zip_path = os.path.join(output_dir, zip_name)
        os.makedirs(output_dir, exist_ok=True)

        try:
            for doc in docs:
                src = doc.get("file_path")
                if src and os.path.isfile(src):
                    fname = doc.get("file_name") or os.path.basename(src)
                    dest = os.path.join(temp_dir, fname)
                    with contextlib.suppress(OSError):
                        shutil.copy2(src, dest)
            shutil.make_archive(zip_path.replace(".zip", ""), "zip", temp_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if os.path.isfile(zip_path):
            logger.info("build_zip: trip %s -> %s (%d bytes)", trip_id, zip_path,
                         os.path.getsize(zip_path))
            return zip_path
        return None

    # ── Combined PDF ─────────────────────────────────────────────────

    def build_combined_pdf(self, trip_id: int, output_dir: str) -> str | None:
        """Merge all trip documents into a single PDF with a cover page.

        Returns the path to the combined PDF, or ``None`` on failure.
        """
        from pypdf import PdfReader, PdfWriter

        docs = self.list_trip_documents(trip_id)
        if not docs:
            return None

        pdf_name = f"trip_{trip_id}_{datetime.now().strftime('%Y%m%d')}_combined.pdf"
        pdf_path = os.path.join(output_dir, pdf_name)
        os.makedirs(output_dir, exist_ok=True)

        writer = PdfWriter()

        # Insert cover page.
        cover = self._generate_cover_page(trip_id, docs)
        if cover:
            writer.add_page(cover)

        for doc in docs:
            src = doc.get("file_path")
            if not src or not os.path.isfile(src):
                continue
            ext = os.path.splitext(src)[1].lower()
            if ext == ".pdf":
                try:
                    reader = PdfReader(src)
                    for page in reader.pages:
                        writer.add_page(page)
                except Exception as exc:
                    logger.warning("build_combined_pdf: skipping PDF %s: %s", src, exc)
            else:
                # Non-PDF file — convert to PDF page using img2pdf or Pillow
                try:
                    import img2pdf
                    img_pdf = img2pdf.convert(src)
                    import io as _io
                    img_reader = PdfReader(_io.BytesIO(img_pdf))
                    for page in img_reader.pages:
                        writer.add_page(page)
                except ImportError:
                    try:
                        from PIL import Image as _pil
                        _pil_img = _pil.open(src).convert("RGB")
                        import io as _io2
                        _buf = _io2.BytesIO()
                        _pil_img.save(_buf, format="PDF")
                        _buf.seek(0)
                        img_reader2 = PdfReader(_buf)
                        for page in img_reader2.pages:
                            writer.add_page(page)
                    except Exception as exc2:
                        logger.warning(
                            "build_combined_pdf: skipping non-PDF %s: %s",
                            src, exc2,
                        )
                except Exception as exc:
                    logger.warning(
                        "build_combined_pdf: skipping non-PDF %s: %s",
                        src, exc,
                    )

        if writer.pages:
            try:
                with open(pdf_path, "wb") as fh:
                    writer.write(fh)
            except Exception as exc:
                logger.warning("build_combined_pdf: write failed: %s", exc)
                return None
            logger.info("build_combined_pdf: trip %s -> %s (%d pages)",
                         trip_id, pdf_path, len(writer.pages))
            return pdf_path
        return None

    def _generate_cover_page(self, trip_id: int, docs: list[dict[str, Any]]):
        """Generate a cover page (PdfPage) with trip summary.

        Uses reportlab to draw the cover, then returns a PyPDF2-compatible
        page.  Falls back to ``None`` when reportlab is not installed.
        """
        try:
            from pypdf import PdfReader
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.pdfgen import canvas as rl_canvas
        except ImportError:
            return None

        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), f"cover_{trip_id}.pdf")
        c = rl_canvas.Canvas(tmp, pagesize=A4)
        _w, h = A4

        c.setFont("Helvetica-Bold", 20)
        c.drawString(2 * cm, h - 2 * cm, f"Trip #{trip_id} — Document Package")

        c.setFont("Helvetica", 11)
        y = h - 4 * cm
        c.drawString(2 * cm, y, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        y -= 0.8 * cm
        c.drawString(2 * cm, y, f"Documents: {len(docs)}")

        y -= 1.5 * cm
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2 * cm, y, "Contents:")
        y -= 0.6 * cm
        c.setFont("Helvetica", 10)
        for doc in docs:
            name = doc.get("file_name") or doc.get("title") or f"Doc #{doc.get('id')}"
            c.drawString(2.5 * cm, y, f"- {name}")
            y -= 0.5 * cm
            if y < 2 * cm:
                c.showPage()
                y = h - 2 * cm

        c.save()
        try:
            reader = PdfReader(tmp)
            return reader.pages[0]
        except Exception:
            return None
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
