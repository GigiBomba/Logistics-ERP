#!/usr/bin/env python
"""CI Gate Script — Operion AI Co-Pilot architectural boundary enforcement.

Runs 5 checks:
  1. No raw SQL/ORM inside backend/copilot/tools/
  2. No vendor SDK imports outside backend/copilot/llm/providers/
  3. No hardcoded English strings where i18n message_key is expected
  4. All language JSON files have a "copilot" namespace
  5. Golden conversation regression suite (§23.4) — re-run whenever planner
     intent patterns, prompt files, the LLM prompt constants
     (TOOL_LOOP_SYSTEM_PROMPT / SYSTEM_PROMPT / _JSON_OUTPUT_FORMAT_CLAUSE —
     AST-extracted from .py, see LLM_PROMPT_CONSTANTS), or the golden suite
     version change since the last validated run, tracked by a content hash
     stored in scripts/.golden_baseline.json

Exits 0 on success, 1 on any violation.

Blueprint references: §19, §23.2, §20, §3.1, §25, §23.4
"""
from __future__ import annotations


import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
COLLECTED_VIOLATIONS: List[str] = []

# ── §23.4 Golden regression gate configuration ─────────────────────────────
GOLDEN_SUITE_RELPATH = "tests/copilot/test_golden_regression.py"
GOLDEN_BASELINE_FILE = ROOT / "scripts" / ".golden_baseline.json"
GOLDEN_SUITE_TIMEOUT_S = 900
# Prompt/template/config extensions the gate treats as prompt inputs. A
# prompt shipped under backend/copilot/ must use one of these extensions or
# it will not invalidate the baseline (list is conservative on purpose).
PROMPT_FILE_GLOBS = (
    "*.txt", "*.md", "*.prompt", "*.template",
    "*.jinja", "*.j2", "*.mustache", "*.tmpl",
    "*.json", "*.yaml", "*.yml",
)


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


# ── Check 5: Golden conversation regression suite (§23.4) ─────────────────

def _extract_intent_patterns(planner_path: Path) -> str:
    """Return a canonical, hashable repr of planner.py's INTENT_PATTERNS.

    Read via the AST (never imported) so the gate stays hermetic — no backend
    code is executed. repr() of the literal is deterministic for nested
    lists/tuples/str, so it is safe to feed into the change hash. Handles
    both plain (``INTENT_PATTERNS = ...``) and annotated module-level
    assignments (``INTENT_PATTERNS: List[tuple] = ...``).
    """
    tree = ast.parse(planner_path.read_text(encoding="utf-8"), filename=str(planner_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "INTENT_PATTERNS" and node.value is not None:
                return repr(ast.literal_eval(node.value))
    raise RuntimeError("INTENT_PATTERNS assignment not found")


def _extract_golden_suite_version(test_path: Path) -> str:
    """Read GOLDEN_SUITE_VERSION from the golden suite without importing it."""
    match = re.search(
        r'GOLDEN_SUITE_VERSION\s*=\s*["\']([^"\']+)["\']',
        test_path.read_text(encoding="utf-8"),
    )
    if not match:
        raise RuntimeError("GOLDEN_SUITE_VERSION not found in golden suite")
    return match.group(1)


# ── LLM prompt constants (§23.4, Gate 3 risk 3) ────────────────────────────
# LLM behavior-defining prompt constants live in .py files, which
# PROMPT_FILE_GLOBS deliberately excludes — without hashing them, prompt
# drift could ship without forcing a golden re-run.  Each entry is
# (relative path, constant name); the source text is AST-extracted (never
# imported) and folded into the golden change hash.
LLM_PROMPT_CONSTANTS: Tuple[Tuple[str, str], ...] = (
    ("backend/copilot/llm/chat.py", "TOOL_LOOP_SYSTEM_PROMPT"),
    ("backend/copilot/llm/chat.py", "SYSTEM_PROMPT"),
    ("backend/copilot/llm/tool_calling.py", "_JSON_OUTPUT_FORMAT_CLAUSE"),
)


def _extract_str_constant(source_path: Path, name: str) -> str:
    """Return a canonical, hashable repr of a module-level str constant via AST.

    Read via the AST (never imported) so the gate stays hermetic — no backend
    code is executed.  Handles plain and annotated assignments and implicit
    string concatenation (the prompt constants are built from adjacent
    literals), which ast.literal_eval folds into a single str.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = node.targets
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name and node.value is not None:
                return repr(ast.literal_eval(node.value))
    raise RuntimeError(f"{name} assignment not found in {source_path.name}")


def _collect_prompt_files() -> List[Path]:
    """Any prompt/template/config files found under backend/copilot/."""
    copilot_dir = ROOT / "backend" / "copilot"
    if not copilot_dir.is_dir():
        return []
    found = set()
    for pattern in PROMPT_FILE_GLOBS:
        found.update(copilot_dir.rglob(pattern))
    return sorted(found)


def compute_prompt_change_hash() -> Tuple[Optional[str], List[str]]:
    """Hash everything the golden suite is sensitive to.

    Inputs: planner.py INTENT_PATTERNS literal, the content of every
    prompt/template file under backend/copilot/, the LLM prompt constants
    (TOOL_LOOP_SYSTEM_PROMPT / SYSTEM_PROMPT / _JSON_OUTPUT_FORMAT_CLAUSE —
    AST-extracted, see LLM_PROMPT_CONSTANTS), and GOLDEN_SUITE_VERSION
    (a suite expansion must invalidate the baseline too).

    Returns (hash, problems). A non-empty ``problems`` list means a required
    input could not be read — the caller MUST then force the golden suite to
    run and MUST NOT refresh the baseline, so the gate never silently skips
    on an unreadable input.
    """
    hasher = hashlib.sha256()
    problems: List[str] = []

    try:
        hasher.update(b"intent_patterns=")
        hasher.update(
            _extract_intent_patterns(ROOT / "backend" / "copilot" / "planner.py").encode("utf-8")
        )
    except Exception as exc:
        problems.append(f"[GOLDEN] cannot hash planner INTENT_PATTERNS: {exc}")

    try:
        hasher.update(b"|prompt_files:")
        for prompt_file in _collect_prompt_files():
            rel = str(prompt_file.relative_to(ROOT)).replace("\\", "/")
            hasher.update(f"|{rel}=".encode("utf-8"))
            hasher.update(prompt_file.read_bytes())
    except Exception as exc:
        problems.append(f"[GOLDEN] cannot hash prompt files under backend/copilot/: {exc}")

    # LLM prompt constants live in .py files (excluded from PROMPT_FILE_GLOBS)
    # — a change here must invalidate the baseline like any other prompt input.
    try:
        hasher.update(b"|llm_prompt_constants:")
        for rel, name in LLM_PROMPT_CONSTANTS:
            hasher.update(f"|{rel}:{name}=".encode("utf-8"))
            hasher.update(_extract_str_constant(ROOT / rel, name).encode("utf-8"))
    except Exception as exc:
        problems.append(f"[GOLDEN] cannot hash LLM prompt constants: {exc}")

    try:
        hasher.update(b"|suite_version=")
        hasher.update(_extract_golden_suite_version(ROOT / GOLDEN_SUITE_RELPATH).encode("utf-8"))
    except Exception as exc:
        problems.append(f"[GOLDEN] cannot read golden suite version: {exc}")

    return hasher.hexdigest(), problems


def _read_baseline() -> Optional[str]:
    """Return the stored prompt_hash, or None when absent/corrupt."""
    try:
        data = json.loads(GOLDEN_BASELINE_FILE.read_text(encoding="utf-8"))
        return data.get("prompt_hash")
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return None


def _write_baseline(prompt_hash: str, suite_version: str) -> None:
    """Persist the validated prompt hash. Called ONLY after a passing run."""
    payload = {
        "prompt_hash": prompt_hash,
        "suite_version": suite_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    GOLDEN_BASELINE_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_golden_suite() -> Tuple[int, str]:
    """Run the golden regression suite via the repo python (subprocess).

    ``-n 0`` disables the repo-wide xdist default (-n auto), which is flaky
    for this suite on the dev machine (§23.4). Non-zero exit ⇒ failure.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        GOLDEN_SUITE_RELPATH, "-q", "-n", "0",
    ]
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(timeout=GOLDEN_SUITE_TIMEOUT_S)
        return proc.returncode, (stdout or "") + (stderr or "")
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        message = (stdout or "") + (stderr or "")
        message += f"\n[GOLDEN] golden suite timed out after {GOLDEN_SUITE_TIMEOUT_S}s and was killed\n"
        return 124, message


def check_golden_regression() -> None:
    """§23.4 gate: run the golden conversation regression suite.

    Run policy (the gate NEVER silently skips):
      * baseline missing/corrupt                    → force a run
      * INTENT_PATTERNS / prompt files changed (or
        golden suite version bumped)                → force a run
      * a hash input is unreadable                  → force a run + violation
      * the previous run failed (baseline not
        written, so the hash cannot match)          → force a run again
      * hash unchanged since a passing run          → skip, with explicit msg

    The baseline is refreshed ONLY on a passing run.
    """
    prompt_hash, problems = compute_prompt_change_hash()
    for problem in problems:
        violation(problem)

    stored_hash = _read_baseline()
    if stored_hash and prompt_hash and stored_hash == prompt_hash and not problems:
        print(
            f"[PASS] Golden regression (23.4): prompt inputs unchanged since last "
            f"validated run (baseline {stored_hash[:12]}...) - suite not re-run"
        )
        return

    if problems:
        reason = "baseline hash inputs unreadable"
    elif not stored_hash:
        reason = "no baseline recorded"
    else:
        reason = "planner INTENT_PATTERNS / prompt files / suite version changed"
    print(f"[GOLDEN] Prompt-change hook (23.4): {reason} - running golden regression suite ...")

    returncode, output = run_golden_suite()

    if returncode == 0:
        passed = re.search(r"(\d+)\s+passed", output)
        summary = f"{passed.group(1)} tests passed" if passed else "passed"
        if prompt_hash and not problems:
            suite_version = _extract_golden_suite_version(ROOT / GOLDEN_SUITE_RELPATH)
            try:
                _write_baseline(prompt_hash, suite_version)
                print(
                    f"[PASS] Golden regression (23.4): {summary} - "
                    f"baseline refreshed ({GOLDEN_BASELINE_FILE.name})"
                )
            except Exception as exc:
                violation(f"[GOLDEN] golden suite passed but baseline could not be written: {exc}")
        else:
            print(
                f"[PASS] Golden regression (23.4): {summary} - "
                "baseline NOT refreshed (hash inputs unreadable)"
            )
    else:
        print(output)
        violation(
            f"[GOLDEN] Golden regression suite failed (exit {returncode}) - "
            "see pytest output above; baseline NOT refreshed, will re-run on next gate"
        )


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    check_no_raw_sql()
    check_vendor_sdk_isolation()
    check_no_hardcoded_english()
    check_copilot_i18n_namespace()
    check_golden_regression()

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
