#!/usr/bin/env python3
"""Static UI style gate for the Operion PySide6 ERP (Phase 1, Lane C).

Read-only linter over the ``ui/`` tree. Enforces five checks:

  1. inline_qss      - ``setStyleSheet(`` calls anywhere in ui/
  2. raw_hex_colors  - ``#[0-9a-fA-F]{3,8}`` literals in ui/
  3. sub_10px_fonts  - ``font-size: <10px`` in QSS/HTML strings in ui/
  4. fixed_geometry  - ``setFixedSize(`` in ui/dialogs/ and ui/widgets/
                       (WARNING only -- never fails the gate; Phase 2
                       will address these)
  5. role_inventory  - cross-file attribute inventory: QSS selectors
                       ``[attr="val"]`` in ui/theme_engine.py that have no
                       ``setProperty("attr", "val")`` setter anywhere in
                       ui/ (dead), setProperty attrs/values with no matching
                       theme selector (unstyled), and attribute names that
                       collide with built-in QWidget property names (the
                       ``size`` collision class).

Checks 1-3 and 5 are graded against a baseline file (default
``tools/ui_style_gate_baseline.json``, override with ``--baseline``):

  * a violation present in the baseline is grandfathered (OK);
  * a violation NOT in the baseline is an ERROR (exit code 1);
  * a baseline entry that no longer matches any current violation is a
    WARNING (stale baseline -- suggests ``--baseline-generate``).

CLI:
  python tools/ui_style_gate.py                      run the gate
  python tools/ui_style_gate.py --baseline-generate  rewrite baseline from current state
  python tools/ui_style_gate.py --report             print all current violations (baseline-aware)
  python tools/ui_style_gate.py --baseline <path>    use a custom baseline file

Pure stdlib (no third-party dependencies).  Runs from any cwd (repo root is
derived from ``__file__``).  Windows-friendly UTF-8 output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_ROOT = REPO_ROOT / "ui"
DEFAULT_BASELINE = REPO_ROOT / "tools" / "ui_style_gate_baseline.json"

# Directory names always skipped while walking the tree.
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".hg",
    ".svn",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "venv",
    ".venv",
    "src",
}

CHECK1_NAME = "inline_qss"
CHECK2_NAME = "raw_hex_colors"
CHECK3_NAME = "sub_10px_fonts"
CHECK4_NAME = "fixed_geometry"
CHECK5_NAME = "role_inventory"

# Checks 1-3 and 5 are baseline-graded; check 4 is informational (warning only).
GRADED_CHECKS = (CHECK1_NAME, CHECK2_NAME, CHECK3_NAME, CHECK5_NAME)
WARNING_CHECKS = (CHECK4_NAME,)

CHECK1_REGEX = re.compile(r"setStyleSheet\(")
CHECK2_REGEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
CHECK3_REGEX = re.compile(r"font-size:\s*(0?[0-9])(\.[0-9]+)?px")
CHECK4_REGEX = re.compile(r"setFixedSize\(")
# Check 5: string-literal setProperty("attr", "val") and QSS attribute selectors.
CHECK5_SETPROP_REGEX = re.compile(
    r'setProperty\(\s*["\']([A-Za-z][A-Za-z0-9_]*)["\']\s*,\s*["\']([^"\']+)["\']'
)
CHECK5_SELECTOR_REGEX = re.compile(
    r"\[([A-Za-z][A-Za-z0-9_-]*)=[\"']([^\"']+)[\"']\]"
)
# Receiver of a ``setProperty`` call (identifier chain before ``.setProperty(``).
CHECK5_RECEIVER_REGEX = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.]*)\s*\.\s*setProperty\("
)
# Warning label for the ``fontRole`` type-mismatch heuristic (warnings only,
# never a gate failure and never added to the baseline).
CHECK5_TM_LABEL = "type-mismatch(fontRole)"

# Check 5c: attribute names that collide with built-in QWidget property names.
# Never use these as QSS attributes (see the role catalog in ui/theme_engine.py).
CHECK5_DENYLIST = {
    "size", "width", "height", "pos", "geometry", "visible", "enabled",
    "font", "cursor", "minimumWidth", "minimumHeight", "maximumWidth",
    "maximumHeight", "fixedWidth", "fixedHeight", "objectName",
}

# (file, line, code) -> sub-check label, set by _collect_role_inventory so the
# report/summary can annotate entries. Kept module-level: this is a CLI tool.
ROLE_ENTRY_LABELS: dict[tuple[str, int, str], str] = {}

# HARD allowlists -- these files are NEVER flagged by the gate.
# Check 1 (inline QSS): central theming files + the receipt print-preview
# HTML builder, plus any file whose *name* contains "print" or "oauth".
CHECK1_ALLOW_REL = {
    "ui/theme_engine.py",
    "ui/stylesheet.py",
    "ui/plotly_theme.py",
    "ui/views/receipt_editor/editor_form.py",
}
# Check 2 (raw hex colors): design-token sources, central styles, plotly
# theme, ui/map/ (map HTML/JS), plus print/oauth-named files.
CHECK2_ALLOW_REL = {
    "ui/theme_engine.py",
    "ui/stylesheet.py",
    "ui/design_tokens.py",
    "ui/plotly_theme.py",
}
CHECK2_ALLOW_DIRS = ("ui/map",)
# Check 3 (sub-10px fonts): print/oauth-named files only.
CHECK3_ALLOW_REL: set[str] = set()


def _filename_exempt(name: str) -> bool:
    """Files whose *name* contains 'print' or 'oauth' are exempt (print/export HTML)."""
    low = name.lower()
    return "print" in low or "oauth" in low


def _is_allowed(check: str, rel: str, name: str) -> bool:
    """Return True when *rel* is on the HARD allowlist for *check*."""
    if _filename_exempt(name):
        return True
    if check == CHECK1_NAME:
        return rel in CHECK1_ALLOW_REL
    if check == CHECK2_NAME:
        if rel in CHECK2_ALLOW_REL:
            return True
        return any(rel == d or rel.startswith(d + "/") for d in CHECK2_ALLOW_DIRS)
    if check == CHECK3_NAME:
        return rel in CHECK3_ALLOW_REL
    return False


def _sort_key(entry: tuple) -> tuple:
    """Deterministic sort for (file, line, code) tuples."""
    return (entry[0], entry[1], entry[2])


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _scan_file(path: Path, rel: str) -> dict[str, list[tuple[int, str]]]:
    """Scan one .py file.

    Returns {check_name: [(line_no, code), ...]} with 1-based line numbers.
    ``code`` is the rstrip'd source line (used for baseline matching).
    """
    found: dict[str, list[tuple[int, str]]] = {
        c: [] for c in (*GRADED_CHECKS, *WARNING_CHECKS)
    }
    seen: dict[str, set[tuple[int, str]]] = {c: set() for c in found}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"cannot read {rel}: {exc}") from exc

    name = path.name
    is_fixed_geometry_scope = rel.startswith("ui/dialogs/") or rel.startswith("ui/widgets/")

    for idx, raw in enumerate(text.splitlines(), 1):
        code = raw.rstrip()

        if not _is_allowed(CHECK1_NAME, rel, name) and CHECK1_REGEX.search(raw):
            key = (idx, code)
            if key not in seen[CHECK1_NAME]:
                seen[CHECK1_NAME].add(key)
                found[CHECK1_NAME].append(key)

        if not _is_allowed(CHECK2_NAME, rel, name) and CHECK2_REGEX.search(raw):
            key = (idx, code)
            if key not in seen[CHECK2_NAME]:
                seen[CHECK2_NAME].add(key)
                found[CHECK2_NAME].append(key)

        match3 = CHECK3_REGEX.search(raw)
        if match3 and not _is_allowed(CHECK3_NAME, rel, name):
            value = float((match3.group(1) or "0") + (match3.group(2) or ""))
            if value < 10:
                key = (idx, code)
                if key not in seen[CHECK3_NAME]:
                    seen[CHECK3_NAME].add(key)
                    found[CHECK3_NAME].append(key)

        if is_fixed_geometry_scope and CHECK4_REGEX.search(raw):
            key = (idx, code)
            if key not in seen[CHECK4_NAME]:
                seen[CHECK4_NAME].add(key)
                found[CHECK4_NAME].append(key)

    return found


def _iter_ui_files():
    """Yield ``(path, rel)`` for every .py file under ui/ (deterministic order)."""
    if not UI_ROOT.is_dir():
        raise RuntimeError(f"UI root not found: {UI_ROOT}")
    for path in sorted(UI_ROOT.rglob("*.py")):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        yield path, rel


def _read_lines(path: Path, rel: str) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot read {rel}: {exc}") from exc


def _collect_role_inventory() -> tuple[list[dict], list[dict]]:
    """Collect Check 5 (``role_inventory``) violations + type-mismatch warnings.

    Cross-file inventory over the ``setProperty("attr", "val")`` call sites in
    ``ui/`` and the QSS attribute selectors ``[attr="val"]`` in
    ``ui/theme_engine.py``:

      a. Dead selector     - a theme selector attr/val with no matching
                             setProperty anywhere in ``ui/``.
      b. Unstyled property - a setProperty attr/val with no matching theme
                             selector.
      c. Built-in denylist - a setProperty or selector attribute name that
                             collides with a built-in QWidget property name.

    Each violation is ``{"file", "line", "code"}`` so it participates in the
    same baseline mechanism as checks 1-3.  Per-entry sub-check labels are
    recorded in ``ROLE_ENTRY_LABELS`` for the report/summary output.

    WARNING (non-blocking, never baselined): ``fontRole`` type-mismatch.
    ``fontRole`` selectors are QLabel-scoped, so a ``setProperty("fontRole", ...)``
    on a non-QLabel widget is a silent no-op.  This heuristic flags any
    ``fontRole`` setter whose receiver is not PROVABLY a QLabel:

      * the setter line itself mentions ``QLabel`` / ``Label(``, or
      * a backward assignment ``<receiver> = <rhs>`` (up to 300 lines) has a
        RHS mentioning ``QLabel`` / ``Label(``.

    LIMITATIONS: string-literal values only; line-scoped with a backward
    assignment scan — receivers constructed in other files, via aliasing or
    indirection, or with a RHS that doesn't spell ``QLabel``/``Label(`` are
    reported as potential mismatches (conservative; may include false
    positives).  Warnings never fail the gate and are not baseline entries.
    """
    setprop_sites: dict[tuple[str, str], set[tuple[str, int, str]]] = {}
    selector_sites: dict[tuple[str, str], set[tuple[str, int, str]]] = {}
    tm_warnings: list[dict] = []
    for path, rel in _iter_ui_files():
        lines = _read_lines(path, rel)
        for idx, raw in enumerate(lines, 1):
            code = raw.rstrip()
            for m in CHECK5_SETPROP_REGEX.finditer(raw):
                key = (m.group(1), m.group(2))
                setprop_sites.setdefault(key, set()).add((rel, idx, code))
                if m.group(1) == "fontRole" and not _fontrole_receiver_is_qlabel(
                    raw, lines, idx
                ):
                    tm_warnings.append({
                        "check": CHECK5_TM_LABEL,
                        "file": rel, "line": idx, "code": code,
                    })
            if rel == "ui/theme_engine.py":
                for m in CHECK5_SELECTOR_REGEX.finditer(raw):
                    key = (m.group(1), m.group(2))
                    selector_sites.setdefault(key, set()).add((rel, idx, code))

    # ROLES is the mutable global used to annotate report output.
    global ROLE_ENTRY_LABELS
    ROLE_ENTRY_LABELS = {}

    violations: list[dict] = []

    def _flag(label: str, sites: set[tuple[str, int, str]]) -> None:
        for rel, idx, code in sorted(sites):
            key = (rel, idx, code)
            ROLE_ENTRY_LABELS[key] = label
            violations.append({"file": rel, "line": idx, "code": code})

    # (a) Dead selectors: theme selector pair with no setter anywhere.
    for key, sites in sorted(selector_sites.items()):
        if key not in setprop_sites:
            _flag("dead", sites)
    # (b) Unstyled properties: setter pair with no theme selector.
    for key, sites in sorted(setprop_sites.items()):
        if key not in selector_sites:
            _flag("unstyled", sites)
    # (c) Built-in name denylist (both sides).
    for key, sites in sorted(setprop_sites.items()):
        if key[0] in CHECK5_DENYLIST:
            _flag("denylist", sites)
    for key, sites in sorted(selector_sites.items()):
        if key[0] in CHECK5_DENYLIST:
            _flag("denylist", sites)

    # Deduplicate exact (file, line, code) tuples (one line can carry two
    # attribute selectors that both resolve to the same source line).
    seen: set[tuple[str, int, str]] = set()
    unique: list[dict] = []
    for v in violations:
        k = (v["file"], v["line"], v["code"])
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return unique, tm_warnings


def _fontrole_receiver_is_qlabel(raw: str, lines: list[str], idx: int) -> bool:
    """Conservative check: is the receiver of this line's ``fontRole`` setter
    provably a QLabel?

    True when the line mentions ``QLabel`` / ``Label(`` itself, or when a
    backward assignment ``<receiver> = <rhs>`` (within 300 lines) has a RHS
    mentioning ``QLabel`` / ``Label(``.  Anything else is reported as a
    potential type mismatch (see the heuristic limitations above).
    """
    if "QLabel" in raw or "Label(" in raw:
        return True
    rm = CHECK5_RECEIVER_REGEX.search(raw)
    if rm is None:
        return False
    receiver = rm.group(1)
    assign = re.compile(r"^\s*" + re.escape(receiver) + r"\s*=\s*([^#;]*)")
    for prev in range(idx - 1, max(0, idx - 300) - 1, -1):
        m = assign.search(lines[prev - 1])
        if m is not None:
            rhs = m.group(1)
            return "QLabel" in rhs or "Label(" in rhs
    return False


def collect_violations() -> tuple[dict[str, list[dict]], list[dict]]:
    """Walk ui/ and return (violations, warnings).

    violations: {check_name: [{"file", "line", "code"}, ...]} for graded checks.
    warnings:   [{"check", "file", "line", "code"}, ...] for the
                ``fixed_geometry`` and ``type-mismatch(fontRole)`` sub-checks.
    """
    violations: dict[str, list[dict]] = {c: [] for c in GRADED_CHECKS}
    warnings: list[dict] = []

    for path, rel in _iter_ui_files():
        per_check = _scan_file(path, rel)
        for check in GRADED_CHECKS:
            for line_no, code in per_check[check]:
                violations[check].append({"file": rel, "line": line_no, "code": code})
        for line_no, code in per_check[CHECK4_NAME]:
            warnings.append({"check": CHECK4_NAME, "file": rel, "line": line_no, "code": code})

    # Check 5 is a global cross-file analysis (not per-file scalar regex).
    # ``_collect_role_inventory`` returns (violations, type-mismatch warnings);
    # the warnings are informational only and never become baseline entries.
    check5_violations, tm_warnings = _collect_role_inventory()
    violations[CHECK5_NAME] = check5_violations
    warnings.extend(tm_warnings)

    return violations, warnings


# ---------------------------------------------------------------------------
# Baseline handling
# ---------------------------------------------------------------------------


def _violation_key(entry: dict) -> tuple[str, int, str]:
    return (entry["file"], entry["line"], entry["code"])


def load_baseline(path: Path) -> dict[str, set[tuple[str, int, str]]]:
    """Load baseline into {check: set of (file, line, code)}.

    A missing baseline file is treated as an empty baseline.  A malformed
    baseline raises RuntimeError (internal error -> exit code 1).
    """
    baseline: dict[str, set[tuple[str, int, str]]] = {}
    if not path.exists():
        return baseline
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot parse baseline file {path}: {exc}") from exc

    violations = raw.get("violations") if isinstance(raw, dict) else None
    if not isinstance(violations, dict):
        raise RuntimeError(
            f"baseline file {path} is malformed: expected {{'violations': {{...}}}}"
        )
    for check, entries in violations.items():
        baseline[check] = set()
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            file_ = entry.get("file")
            line = entry.get("line")
            code = entry.get("code")
            if isinstance(file_, str) and isinstance(line, int) and isinstance(code, str):
                baseline[check].add((file_, line, code))
    return baseline


def save_baseline(path: Path, violations: dict[str, list[dict]]) -> None:
    """Write the baseline file from the current violation state."""
    payload = {
        "violations": {
            check: sorted(violations[check], key=_violation_key)
            for check in sorted(violations)
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def analyze(
    violations: dict[str, list[dict]],
    baseline: dict[str, set[tuple[str, int, str]]],
) -> dict[str, dict]:
    """Compare current violations against the baseline.

    Returns {check: {"current", "new", "grandfathered", "stale"}} where each
    value is a set of (file, line, code) tuples.
    """
    result: dict[str, dict] = {}
    for check in GRADED_CHECKS:
        current = {_violation_key(v) for v in violations[check]}
        base = baseline.get(check, set())
        result[check] = {
            "current": current,
            "new": sorted(current - base, key=_sort_key),
            "grandfathered": current & base,
            "stale": sorted(base - current, key=_sort_key),
        }
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _heading(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def _fmt(key: tuple[str, int, str]) -> str:
    file_, line, code = key
    return f"{file_}:{line}  {code}"


def _warning_counts(warnings: list[dict]) -> dict[str, int]:
    """{check label: count} for the non-blocking warning sub-checks."""
    counts: dict[str, int] = {}
    for w in warnings:
        counts[w["check"]] = counts.get(w["check"], 0) + 1
    return counts


def _print_summary(analysis: dict[str, dict], warnings: list[dict]) -> None:
    print("Summary:")
    for check in GRADED_CHECKS:
        a = analysis[check]
        print(
            f"  {check:<18} current={len(a['current']):>4}  "
            f"grandfathered={len(a['grandfathered']):>4}  "
            f"new={len(a['new']):>4}  stale={len(a['stale']):>4}"
        )
    _print_role_breakdown(analysis)
    for label, count in sorted(_warning_counts(warnings).items()):
        note = " (non-blocking, Phase 2)" if label == CHECK4_NAME else " (non-blocking)"
        print(f"  {label:<26} {count:>4} warning(s){note}")


def _print_role_breakdown(analysis: dict[str, dict]) -> None:
    """Print Check 5 sub-check counts (dead / unstyled / denylist)."""
    current = analysis[CHECK5_NAME]["current"]
    counts = {"dead": 0, "unstyled": 0, "denylist": 0}
    for key in current:
        label = ROLE_ENTRY_LABELS.get(key, "unstyled")
        if label in counts:
            counts[label] += 1
    print(
        f"  role_inventory sub-checks: dead={counts['dead']}  "
        f"unstyled={counts['unstyled']}  denylist={counts['denylist']}"
    )


def print_run(analysis: dict[str, dict], warnings: list[dict]) -> None:
    print("=" * 72)
    print("UI Style Gate -- Phase 1 Lane C (static style enforcement)")
    print("=" * 72)
    print()
    _print_summary(analysis, warnings)

    new_any = any(analysis[c]["new"] for c in GRADED_CHECKS)
    if new_any:
        _heading("NEW violations (gate failing -- not in baseline):")
        for check in GRADED_CHECKS:
            if analysis[check]["new"]:
                print(f"  [{check}]")
                for key in analysis[check]["new"]:
                    print(f"    {_fmt(key)}")

    stale_any = any(analysis[c]["stale"] for c in GRADED_CHECKS)
    if stale_any:
        _heading("Stale baseline entries (no longer match any violation -- run --baseline-generate):")
        for check in GRADED_CHECKS:
            if analysis[check]["stale"]:
                print(f"  [{check}]")
                for key in analysis[check]["stale"]:
                    print(f"    {_fmt(key)}")


def print_report(analysis: dict[str, dict], warnings: list[dict]) -> None:
    print("=" * 72)
    print("UI Style Gate -- REPORT (all current violations, baseline-aware)")
    print("=" * 72)
    print()
    _print_summary(analysis, warnings)

    for check in GRADED_CHECKS:
        a = analysis[check]
        _heading(f"{check}  ({len(a['current'])} current)")
        if not a["current"]:
            print("  (none)")
            continue
        new_set = set(a["new"])
        for key in sorted(a["current"], key=_sort_key):
            tag = "NEW" if key in new_set else "GRANDFATHERED"
            if check == CHECK5_NAME:
                label = ROLE_ENTRY_LABELS.get(key, "?")
                print(f"  [{tag:<13} {label:<9}] {_fmt(key)}")
            else:
                print(f"  [{tag:<13}] {_fmt(key)}")
        if a["stale"]:
            _heading(f"stale baseline entries for {check} ({len(a['stale'])}):")
            for key in a["stale"]:
                print(f"    {_fmt(key)}")

    if warnings:
        _heading(f"Warnings ({len(warnings)} total, non-blocking -- never fail the gate):")
        for label in sorted({w["check"] for w in warnings}):
            for w in (x for x in warnings if x["check"] == label):
                print(f"    [{label}] {w['file']}:{w['line']}  {w['code']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _configure_io() -> None:
    """Windows-friendly UTF-8 output with replacement chars for odd bytes."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _configure_io()

    parser = argparse.ArgumentParser(
        prog="ui_style_gate",
        description="Static UI style gate over the ui/ tree (Phase 1 Lane C).",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE),
        metavar="PATH",
        help="baseline file to compare against (default: %(default)s)",
    )
    parser.add_argument(
        "--baseline-generate",
        action="store_true",
        help="rewrite the baseline file from the current tree and exit 0",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print all current violations grouped by check (baseline-aware) and exit 0",
    )
    args = parser.parse_args(argv)

    baseline_path = Path(args.baseline).resolve()

    try:
        violations, warnings = collect_violations()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.baseline_generate:
        try:
            save_baseline(baseline_path, violations)
        except OSError as exc:
            print(f"ERROR: cannot write baseline {baseline_path}: {exc}", file=sys.stderr)
            return 1
        print(f"Baseline generated: {baseline_path}")
        for check in GRADED_CHECKS:
            print(f"  {check}: {len(violations[check])} violation(s) frozen")
        for label, count in sorted(_warning_counts(warnings).items()):
            print(f"  {label}: {count} warning(s) (not part of the baseline)")
        return 0

    try:
        baseline = load_baseline(baseline_path)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    analysis = analyze(violations, baseline)
    total_new = sum(len(analysis[c]["new"]) for c in GRADED_CHECKS)

    if args.report:
        # Diagnostic mode: print everything, never fail the gate.
        print_report(analysis, warnings)
        print()
        print(f"Gate: PASS -- report only (baseline {baseline_path.name})")
        return 0

    print_run(analysis, warnings)

    if total_new == 0:
        print()
        print(f"Gate: PASS -- no new violations (baseline {baseline_path.name})")
        return 0
    print()
    print(
        f"Gate: FAIL -- {total_new} new violation(s). "
        "Fix them or run --baseline-generate to freeze the current debt."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())