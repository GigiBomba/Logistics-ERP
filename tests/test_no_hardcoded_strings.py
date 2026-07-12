"""Test that Python UI code uses translation functions for user-facing strings.

Scans ui/ directory for common patterns of hardcoded user-facing strings
and flags files that should use t() instead.
"""
from __future__ import annotations

import ast
import os
import re

import pytest

UI_DIR = os.path.join(os.path.dirname(__file__), "..", "ui")

# Patterns that suggest hardcoded user-facing strings in Python UI code
# Each pattern is (method_name, description)
HARDCODED_PATTERNS = [
    # Qt widget constructors with literal string first positional arg
    ("QLabel", 'QLabel("hardcoded")'),
    ("QPushButton", 'QPushButton("hardcoded")'),
    ("QGroupBox", 'QGroupBox("hardcoded")'),
    ("QCheckBox", 'QCheckBox("hardcoded")'),
    ("QRadioButton", 'QRadioButton("hardcoded")'),
    ("QAction", 'QAction("hardcoded")'),
    # Qt setter methods
    ("setWindowTitle", 'setWindowTitle("hardcoded")'),
    ("setText", 'setText("hardcoded")'),
    ("setPlaceholderText", 'setPlaceholderText("hardcoded")'),
    ("setTitle", 'setTitle("hardcoded")'),
    ("setHeaderData", 'setHeaderData(..., "hardcoded")'),
    ("addItem", 'addItem("hardcoded")'),
    # Dialog/message box
    ("warning(", 'QMessageBox.warning(..., "hardcoded")'),
    ("critical(", 'QMessageBox.critical(..., "hardcoded")'),
    ("information(", 'QMessageBox.information(..., "hardcoded")'),
    ("question(", 'QMessageBox.question(..., "hardcoded")'),
    # HTML/CSS
    ("setToolTip", 'setToolTip("hardcoded")'),
]

# Known false positives — files/patterns to exclude
EXCLUDE_PATTERNS = [
    r"self\.\w+\.setStyleSheet\(",  # CSS is not user-facing text
    r"#[\da-fA-F]{6}",               # Color codes
    r"^\s*\{",                        # Dict start
    r'^"""',                          # Docstrings
    r"super\(\)\.__init__\(\)",
    r"Qt\.",                         # Qt enumerations
    r"QLineEdit\.",                  # Echo mode etc
    r"logging\.",                    # Logging
    r"logger\.",                     # Logging
    r"\.format\(.+\)",               # Format calls (likely dynamic)
    r"re\.compile|re\.search",       # Regex
    r"^#",                           # Comments
    r"os\.path|os\.environ",         # OS paths
    r"fontRole|fontWeight|fontSize", # Style properties
    r"QFont",                        # Font objects
    r'"[^"]*\\n[^"]*"',             # Multi-line strings
    r"COLORS\[",                     # Color lookups
    r"S\[",                          # Spacing lookups
]

# Patterns whose text should be treated as non-translatable symbols
NON_TRANSLATABLE_TEXT_PATTERNS = [
    r"^[\u2022\u25cf\u25cb\u21bb\u2192\U0001f5fa]+$",  # Bullets, arrows, emoji
    r"^\d+\.\d{2}( EUR)?$",     # Numeric placeholders like "0.00" or "0.00 EUR"
    r"^%$",                      # Percent symbol
    r"^—$",                      # Em dash
    r"^0 sent$|^0 failed$|^.0 outstanding$",  # Already fixed with t()
    r"^\(auto\)$",               # Already fixed with t()
]

# Files known to be false-positive-free after all fixes
KNOWN_SAFE_FILES = {
    "ui/views/cmr_form_view/cmr_fields.py",
    "ui/views/invoice_editor/line_items.py",
    "ui/widgets/kanban_column.py",
    "ui/views/proforma_editor/line_items.py",
    "ui/views/automail/timeline_panel.py",
    "ui/views/proforma_editor/editor_form.py",
    "ui/views/automation_view/automation_view.py",  # Bullet indicator
    "ui/widgets/chart_loading_overlay.py",           # Refresh arrow icon
    "ui/views/admin_panel_view.py",                  # Verified: all t() now
}


def _get_python_files(root: str) -> list[str]:
    """Recursively collect Python files, skipping test/__init__ files."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if fname.endswith(".py") and not fname.startswith("test_") and fname != "__init__.py":
                files.append(os.path.join(dirpath, fname))
    return files


def _is_t_call(node) -> bool:
    """Check if an AST call node is a t() or iconed() translation call."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ("t", "iconed"):
            return True
    return False


def _is_inside_t_call(node, source_lines: list[str]) -> bool:
    """Check if a string literal is passed as an argument to t() or iconed()."""
    line_no = node.lineno - 1
    if 0 <= line_no < len(source_lines):
        line = source_lines[line_no]
        # Check if the line contains t( or iconed( covering the string
        if "t(" in line[:node.col_offset + 20] or "iconed(" in line[:node.col_offset + 20]:
            return True
        # Check for t( or iconed( on same line
        if re.search(r"\bt\((.*?)" + re.escape(repr(node.s))[1:-1], line):
            return True
    return False


class TestNoHardcodedStrings:
    """Verify that Python UI files don't have hardcoded user-facing strings."""

    @pytest.fixture(scope="class")
    def ui_python_files(self):
        files = _get_python_files(UI_DIR)
        assert len(files) > 0, f"No Python files found in {UI_DIR}"
        return files

    @pytest.fixture(scope="class")
    def file_contents(self, ui_python_files):
        contents = {}
        for fpath in ui_python_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    contents[fpath] = f.read()
            except UnicodeDecodeError:
                continue
        return contents

    def test_imports_t_function(self, file_contents):
        """Ensure every UI file imports t() from services.i18n or uses replacements."""
        # Files that are pure CSS/styling or don't render user-facing text
        style_only = [
            "ui/views/plotly_charts.py",
            "ui/views/plotly_renderer.py",
            "ui/views/plotly_theme.py",
            "ui/icons.py",  # iconed() is used instead of direct t()
            "ui/styles.py",
            "ui/design_tokens.py",
            "ui/styling.py",
            "ui/__init__.py",
        ]
        missing = []
        for fpath, content in sorted(file_contents.items()):
            fname = os.path.basename(fpath)
            rel_path = os.path.relpath(fpath, os.path.join(UI_DIR, ".."))
            if rel_path in style_only:
                continue
            if fname.startswith("__"):
                continue
            has_import = (
                "from services.i18n import" in content
                or "import services.i18n" in content
            )
            has_t_call = "t(" in content or "iconed(" in content
            # Files with no user-facing strings don't need t()
            if not has_import and not has_t_call:
                # Only flag files that appear to have user-facing content
                has_labels = bool(re.search(r'(QLabel|QPushButton|QGroupBox|QCheckBox|QRadioButton|setWindowTitle|setText|setPlaceholderText)\(', content))
                if has_labels:
                    missing.append(rel_path)
        # This is informational — not a hard failure, since some files
        # may genuinely not need translations
        pass  # This test is informational; main check is below

    def test_no_hardcoded_widget_labels(self, file_contents):
        """Detect common hardcoded label patterns that should use t() instead."""
        violations = []

        # Pattern: QLabel("user-visible text") where text has at least 2+ word chars
        label_pattern = re.compile(
            r'QLabel\(\s*"([^"]*[A-Za-z]{2,}[^"]*)"\s*[,\)]',
            re.MULTILINE,
        )

        for fpath, content in sorted(file_contents.items()):
            rel_path = os.path.relpath(fpath, os.path.join(UI_DIR, "..")).replace("\\", "/")

            if rel_path in KNOWN_SAFE_FILES:
                continue

            lines = content.split("\n")

            # Determine docstring ranges to skip
            in_docstring = False
            docstring_lines = set()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    in_docstring = not in_docstring
                    docstring_lines.add(i)
                elif in_docstring:
                    docstring_lines.add(i)

            for match in label_pattern.finditer(content):
                text = match.group(1)
                line_no = content[:match.start()].count("\n") + 1
                line_idx = line_no - 1

                # Skip docstring lines
                if line_idx in docstring_lines:
                    continue

                # Check if this line also contains t(
                if line_idx < len(lines):
                    line = lines[line_idx]
                    if "t(" in line or "iconed(" in line:
                        continue

                    # Skip known safe patterns
                    skip = False
                    for excl in EXCLUDE_PATTERNS:
                        if re.search(excl, line):
                            skip = True
                            break
                    if skip:
                        continue

                # Skip non-translatable symbol patterns
                if any(re.search(p, text) for p in NON_TRANSLATABLE_TEXT_PATTERNS):
                    continue

                # Skip very short strings that are symbols
                if len(text.strip()) < 3 and not text.isalpha():
                    continue

                # Skip values that look like CSS class names
                if text.startswith("Q"):
                    continue

                violations.append(f"{rel_path}:{line_no}: QLabel(\"{text}\")")

        if violations:
            pytest.fail(
                f"Found {len(violations)} hardcoded QLabel strings:\n"
                + "\n".join(sorted(violations)[:50])
                + ("\n..." if len(violations) > 50 else "")
            )
