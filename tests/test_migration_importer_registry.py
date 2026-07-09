"""Unit tests for ImporterRegistry and all built-in import format readers."""
from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET

import pytest

from services.migration.importer_registry import (
    CsvImporter,
    ExcelImporter,
    ImporterRegistry,
    JsonImporter,
    XmlImporter,
    _import_registry,
)
from services.migration.types import ImportFormat


# ── Registry tests ───────────────────────────────────────────────────────────


class TestImporterRegistry:
    def test_register_adds_importer(self):
        registry = ImporterRegistry()
        importer = CsvImporter()
        registry.register(importer)
        assert ImportFormat.CSV in registry.supported_formats

    def test_get_returns_correct_importer(self):
        registry = ImporterRegistry()
        registry.register(CsvImporter())
        registry.register(JsonImporter())
        got = registry.get(ImportFormat.CSV)
        assert isinstance(got, CsvImporter)
        got = registry.get(ImportFormat.JSON)
        assert isinstance(got, JsonImporter)

    def test_get_raises_value_error_for_unknown(self):
        registry = ImporterRegistry()
        with pytest.raises(ValueError, match="No importer registered"):
            registry.get(ImportFormat.XML)

    def test_supported_formats_returns_list(self):
        registry = ImporterRegistry()
        assert registry.supported_formats == []
        registry.register(CsvImporter())
        assert registry.supported_formats == [ImportFormat.CSV]

    def test_register_type_error_for_invalid(self):
        registry = ImporterRegistry()
        with pytest.raises(TypeError, match="does not implement ImporterProtocol"):
            registry.register("not an importer")  # type: ignore[arg-type]

    def test_supported_formats_returns_all_registered(self):
        registry = ImporterRegistry()
        registry.register(CsvImporter())
        registry.register(ExcelImporter())
        registry.register(JsonImporter())
        registry.register(XmlImporter())
        fmts = registry.supported_formats
        assert len(fmts) == 4
        assert ImportFormat.CSV in fmts
        assert ImportFormat.EXCEL in fmts
        assert ImportFormat.JSON in fmts
        assert ImportFormat.XML in fmts


class TestImportRegistrySingleton:
    """Verify the module-level _import_registry has all 4 importers."""

    def test_singleton_has_all_importers(self):
        assert ImportFormat.CSV in _import_registry.supported_formats
        assert ImportFormat.EXCEL in _import_registry.supported_formats
        assert ImportFormat.JSON in _import_registry.supported_formats
        assert ImportFormat.XML in _import_registry.supported_formats

    def test_singleton_get_returns_importers(self):
        assert isinstance(_import_registry.get(ImportFormat.CSV), CsvImporter)
        assert isinstance(_import_registry.get(ImportFormat.EXCEL), ExcelImporter)
        assert isinstance(_import_registry.get(ImportFormat.JSON), JsonImporter)
        assert isinstance(_import_registry.get(ImportFormat.XML), XmlImporter)


# ── CSV Importer tests ───────────────────────────────────────────────────────


class TestCsvImporter:
    def test_read_returns_rows(self):
        importer = CsvImporter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,email\nAlice,alice@test.com\nBob,bob@test.com\n")
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) == 2
            assert rows[0] == {"name": "Alice", "email": "alice@test.com"}
            assert rows[1] == {"name": "Bob", "email": "bob@test.com"}
        finally:
            import os
            os.unlink(path)

    def test_read_empty_csv(self):
        importer = CsvImporter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", delete=False) as f:
            f.write("name,email\n")
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert rows == []
        finally:
            import os
            os.unlink(path)

    def test_validate_schema_valid(self):
        importer = CsvImporter()
        rows = [{"name": "Alice"}, {"name": "Bob"}]
        assert importer.validate_schema(rows) == []

    def test_validate_schema_empty(self):
        importer = CsvImporter()
        errors = importer.validate_schema([])
        assert len(errors) == 1
        assert "no data" in errors[0].lower()

    def test_validate_schema_invalid_row(self):
        importer = CsvImporter()
        errors = importer.validate_schema([{}, {"name": "Alice"}])
        assert len(errors) >= 1
        assert any("empty" in e.lower() for e in errors)

    def test_format_attribute(self):
        assert CsvImporter().format == ImportFormat.CSV


# ── Excel Importer tests ─────────────────────────────────────────────────────


class TestExcelImporter:
    def test_read_returns_rows(self):
        pytest.importorskip("openpyxl")
        import openpyxl

        importer = ExcelImporter()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "TestSheet"
            ws.append(["name", "email"])
            ws.append(["Alice", "alice@test.com"])
            ws.append(["Bob", "bob@test.com"])
            wb.save(path)
            wb.close()

            rows = importer.read(path)
            assert len(rows) == 2
            assert rows[0] == {"name": "Alice", "email": "alice@test.com"}
            assert rows[1] == {"name": "Bob", "email": "bob@test.com"}
        finally:
            import os
            os.unlink(path)

    def test_read_empty_excel(self):
        pytest.importorskip("openpyxl")
        import openpyxl

        importer = ExcelImporter()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            path = f.name
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["name", "email"])  # headers only
            wb.save(path)
            wb.close()

            rows = importer.read(path)
            assert rows == []
        finally:
            import os
            os.unlink(path)

    def test_validate_schema_valid(self):
        importer = ExcelImporter()
        rows = [{"name": "Alice"}]
        assert importer.validate_schema(rows) == []

    def test_validate_schema_empty(self):
        importer = ExcelImporter()
        errors = importer.validate_schema([])
        assert len(errors) == 1
        assert "no data" in errors[0].lower()

    def test_validate_schema_too_many_rows(self):
        importer = ExcelImporter()
        rows = [{"col": i} for i in range(10001)]
        errors = importer.validate_schema(rows)
        assert any("10000" in e for e in errors)

    def test_format_attribute(self):
        assert ExcelImporter().format == ImportFormat.EXCEL


# ── JSON Importer tests ──────────────────────────────────────────────────────


class TestJsonImporter:
    def test_read_list_root(self):
        importer = JsonImporter()
        data = [{"name": "Alice"}, {"name": "Bob"}]
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) == 2
            assert rows == data
        finally:
            import os
            os.unlink(path)

    def test_read_dict_root(self):
        importer = JsonImporter()
        data = {"a": {"name": "Alice"}, "b": {"name": "Bob"}}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) == 2
            assert {"name": "Alice"} in rows
            assert {"name": "Bob"} in rows
        finally:
            import os
            os.unlink(path)

    def test_read_empty_list(self):
        importer = JsonImporter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump([], f)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert rows == []
        finally:
            import os
            os.unlink(path)

    def test_read_dict_root_with_non_dict_values(self):
        """Dict-of-dicts: non-dict values are skipped."""
        importer = JsonImporter()
        data = {"a": {"name": "Alice"}, "b": "not_a_dict"}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) == 1
            assert rows[0] == {"name": "Alice"}
        finally:
            import os
            os.unlink(path)

    def test_read_raises_on_invalid_root(self):
        importer = JsonImporter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            json.dump("string_root", f)
            f.flush()
            path = f.name
        try:
            with pytest.raises(ValueError, match="JSON root must be"):
                importer.read(path)
        finally:
            import os
            os.unlink(path)

    def test_validate_schema_valid(self):
        importer = JsonImporter()
        assert importer.validate_schema([{"a": 1}]) == []

    def test_validate_schema_empty(self):
        importer = JsonImporter()
        errors = importer.validate_schema([])
        assert len(errors) == 1
        assert "no data" in errors[0].lower()

    def test_format_attribute(self):
        assert JsonImporter().format == ImportFormat.JSON


# ── XML Importer tests ───────────────────────────────────────────────────────


class TestXmlImporter:
    def test_read_returns_rows(self):
        importer = XmlImporter()
        xml_content = """<?xml version="1.0"?>
<root>
    <row>
        <name>Alice</name>
        <email>alice@test.com</email>
    </row>
    <row>
        <name>Bob</name>
        <email>bob@test.com</email>
    </row>
</root>"""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) == 2
            assert rows[0] == {"name": "Alice", "email": "alice@test.com"}
            assert rows[1] == {"name": "Bob", "email": "bob@test.com"}
        finally:
            import os
            os.unlink(path)

    def test_read_fallback_direct_children(self):
        """When no nested child elements exist, falls back to direct children."""
        importer = XmlImporter()
        xml_content = """<?xml version="1.0"?>
<root>
    <item>value1</item>
    <item>value2</item>
</root>"""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert len(rows) >= 1
        finally:
            import os
            os.unlink(path)

    def test_read_empty_xml(self):
        importer = XmlImporter()
        xml_content = """<?xml version="1.0"?><root></root>"""
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".xml", delete=False) as f:
            f.write(xml_content)
            f.flush()
            path = f.name
        try:
            rows = importer.read(path)
            assert rows == []
        finally:
            import os
            os.unlink(path)

    def test_read_raises_on_bad_xml(self):
        importer = XmlImporter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".xml", delete=False) as f:
            f.write("not xml at all")
            f.flush()
            path = f.name
        try:
            with pytest.raises(ValueError, match="Failed to parse XML"):
                importer.read(path)
        finally:
            import os
            os.unlink(path)

    def test_validate_schema_valid(self):
        importer = XmlImporter()
        assert importer.validate_schema([{"a": "1"}]) == []

    def test_validate_schema_empty(self):
        importer = XmlImporter()
        errors = importer.validate_schema([])
        assert len(errors) == 1
        assert "no data" in errors[0].lower()

    def test_format_attribute(self):
        assert XmlImporter().format == ImportFormat.XML
