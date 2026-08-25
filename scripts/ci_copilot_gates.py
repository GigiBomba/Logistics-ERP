#!/usr/bin/env python
"""CI Gate Script — Operion AI Co-Pilot architectural boundary enforcement.

Runs 4 static-analysis checks:
  1. No raw SQL/ORM inside backend/copilot/tools/
  2. No vendor SDK imports outside backend/copilot/llm/providers/
  3. No hardcoded English strings where i18n message_key is expected
  4. All language JSON files have a "copilot" namespace

Exits 0 on success, 1 on any violation.

Blueprint references: §19, §23.2, §20, §3.1, §25
"""
from __future__ import annotations


import json
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent
COLLECTED_VIOLATIONS: List[str] = []


def violation(msg: str) -> None:
    COLLECTED_VIOLATIONS.append(msg)


# ── Check 1: No raw SQL/ORM in tools/ ─────────────────────────────────────

def check_no_raw_sql() -> None:
    """Scan backend/copilot/tools/ for SQL execution patterns per §19.

    Forbidden: direct .execute( calls, session.query, text(, raw cursor usage,
    or importing DatabaseManager. The BaseTool abstract method is exempt.
    """
    tools_dir = ROOT / "backend" / "copilot" / "tools"
    if not tools_dir.is_dir():
        violation("tools/ directory not found")
        return

    forbidden_patterns = [
        (r"\.execute\s*\(", "Raw .execute() call"),
        (r"session\.query\b", "ORM session.query usage"),
        (r"\btext\s*\(", "SQL text() function"),
        (r"\.cursor\b", "Raw cursor access"),
        (r"DatabaseManager", "Direct DatabaseManager import"),
    ]

    for py_file in tools_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        filepath = str(py_file.relative_to(ROOT)).replace("\\", "/")

        for pattern, desc in forbidden_patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for m in matches:
                line_start = max(0, m.start() - 100)
                context = content[line_start:m.end() + 50]
                # Exempt BaseTool's own abstract execute() definition
                if "abstractmethod" in context and "async def execute" in context:
                    continue
                line_no = content[:m.start()].count("\n") + 1
                violation(f"[SQL] {filepath}:{line_no} — {desc}")


# ── Check 2: No vendor SDK outside llm/providers/ ──────────────────────────

def check_vendor_sdk_isolation() -> None:
    """Scan backend/copilot/ (excluding llm/providers/) for vendor SDK imports.

    Only backend/copilot/llm/providers/ may import vendor SDKs directly (§23.2).
    """
    copilot_dir = ROOT / "backend" / "copilot"
    providers_dir = copilot_dir / "llm" / "providers"
    if not copilot_dir.is_dir():
        return

    forbidden_imports = [
        r"from\s+google\.genai\s+import",
        r"import\s+google\.genai",
        r"from\s+google\.generativeai\s+import",
        r"import\s+google\.generativeai",
        r"from\s+anthropic\s+import",
        r"import\s+anthropic",
        r"from\s+openai\s+import",
        r"import\s+openai",
        r"from\s+transformers\s+import",
        r"import\s+transformers",
        r"from\s+torch\s+import",
        r"import\s+torch",
    ]

    for py_file in copilot_dir.rglob("*.py"):
        try:
            py_file.relative_to(providers_dir)
            continue
        except ValueError:
            pass

        content = py_file.read_text(encoding="utf-8")
        filepath = str(py_file.relative_to(ROOT)).replace("\\", "/")

        for pattern in forbidden_imports:
            m = re.search(pattern, content)
            if m:
                line_no = content[:m.start()].count("\n") + 1
                violation(f"[VENDOR] {filepath}:{line_no} — vendor SDK import outside llm/providers/")


# ── Check 3: No hardcoded English in i18n key contexts ─────────────────────

def check_no_hardcoded_english() -> None:
    """Scan backend/copilot/ for English strings where message_key is expected.

    Detects: clarification_question_key, summary_key, message_key assignments
    that contain English prose (words with spaces) instead of i18n dot-notation keys.
    """
    copilot_dir = ROOT / "backend" / "copilot"
    if not copilot_dir.is_dir():
        return

    i18n_key_fields = [
        "clarification_question_key",
        "summary_key",
        "message_key",
        "decision_rationale_key",
        "label",
    ]

    for py_file in copilot_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        filepath = str(py_file.relative_to(ROOT)).replace("\\", "/")

        for field in i18n_key_fields:
            pattern = rf'{field}\s*[:=]\s*["\']([A-Za-z][^"\']*?[a-z] [A-Za-z][^"\']*?)["\']'
            for m in re.finditer(pattern, content):
                value = m.group(1)
                if " " in value and not value.startswith("copilot."):
                    line_no = content[:m.start()].count("\n") + 1
                    violation(f"[i18n] {filepath}:{line_no} — hardcoded English '{value[:60]}...' in {field}")


# ── Check 4: All languages have copilot namespace ──────────────────────────

def check_copilot_i18n_namespace() -> None:
    """Verify every language JSON file in data/translations/ has a 'copilot' key.

    Skip utility files: de_translation_map.json, missing_translations.json.
    """
    translations_dir = ROOT / "data" / "translations"
    if not translations_dir.is_dir():
        return

    skip_files = {"de_translation_map.json", "missing_translations.json"}

    for json_file in sorted(translations_dir.glob("*.json")):
        if json_file.name in skip_files:
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if "copilot" not in data:
                violation(f"[i18n] {json_file.name} — missing 'copilot' namespace. Add: \"copilot\": {{}}")
        except json.JSONDecodeError as exc:
            violation(f"[i18n] {json_file.name} — invalid JSON: {exc}")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    check_no_raw_sql()
    check_vendor_sdk_isolation()
    check_no_hardcoded_english()
    check_copilot_i18n_namespace()

    if COLLECTED_VIOLATIONS:
        print(f"\n[FAIL] {len(COLLECTED_VIOLATIONS)} CI gate violation(s) found:\n")
        for v in COLLECTED_VIOLATIONS:
            print(f"  {v}")
        print("\nFix these violations before merging.")
        return 1

    print("[PASS] All CI gates passed (0 violations)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
