"""Analyze harness geometry dumps for design-token compliance.

Reads every <page>_<state>.json produced by tools/ui_audit_harness.py and flags
layout spacing / contents-margin / font-size values that are NOT on the
design-token scales. Output is evidence-backed (computed geometry) for the
visual audit report.

Usage:
    python tools/analyze_geometry.py [--dir tools/evidence/empty] [--dir ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

SPACING_SCALE = {0, 4, 8, 12, 16, 20, 24, 32, 40, 48, 64}
FONT_SCALE = {10, 11, 12, 13, 16, 22, 26, 32}
# Qt default values that are NOT app deviations (set by Qt, not app code).
QT_DEFAULT_MARGIN = 9
QT_DEFAULT_SPACING = 6
# Fixed heights that are legitimate widget sizes (not spacing).
HEIGHT_ALLOW = {0, 18, 20, 22, 24, 26, 28, 32, 36, 38, 40, 44, 48, 52, 56, 60,
                64, 72, 80, 88, 96, 100, 120, 128, 140, 160, 200, 220, 240,
                260, 280, 300, 320, 340, 360, 380, 400, 440, 480, 520, 560,
                600, 640, 700, 720, 800, 900, 1000}


def analyze_file(path: str) -> list[dict]:
    findings: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            widgets = json.load(fh)
    except Exception as exc:
        return [{"kind": "error", "detail": f"unreadable: {exc}"}]

    for w in widgets:
        cls = w.get("class", "?")
        obj = w.get("objectName", "")
        for lay in w.get("layouts", []):
            spacing = lay.get("spacing")
            if spacing is not None and spacing not in SPACING_SCALE:
                if spacing == -1 or spacing == QT_DEFAULT_SPACING:
                    continue  # Qt default, not an app deviation
                findings.append({
                    "kind": "spacing",
                    "widget": f"{cls}({obj})",
                    "layout": lay.get("class", "?"),
                    "value": spacing,
                    "scale": sorted(SPACING_SCALE),
                })
            margins = lay.get("contentsMargins") or []
            if len(margins) == 4:
                for i, m in enumerate(margins):
                    if m not in SPACING_SCALE:
                        if m == QT_DEFAULT_MARGIN:
                            continue  # Qt default, not an app deviation
                        findings.append({
                            "kind": "margin",
                            "widget": f"{cls}({obj})",
                            "layout": lay.get("class", "?"),
                            "side": ["L", "T", "R", "B"][i],
                            "value": m,
                            "scale": sorted(SPACING_SCALE),
                        })
        font = w.get("font", {})
        ps = font.get("pointSize")
        if ps and ps != -1 and ps not in FONT_SCALE:
            findings.append({
                "kind": "font",
                "widget": f"{cls}({obj})",
                "layout": "",
                "value": ps,
                "scale": sorted(FONT_SCALE),
            })
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", action="append", default=[])
    args = parser.parse_args()
    dirs = args.dir or ["tools/evidence/empty", "tools/evidence/populated"]

    all_findings: dict[str, list[dict]] = {}
    for d in dirs:
        if not os.path.isdir(d):
            print(f"SKIP (no dir): {d}")
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(d, fn)
            findings = analyze_file(path)
            if findings:
                all_findings[fn] = findings

    # Aggregate by kind + value for a compact report.
    from collections import Counter
    agg: Counter = Counter()
    detail: dict[str, list[str]] = {}
    for fn, findings in all_findings.items():
        for f in findings:
            key = f"{f['kind']}={f['value']}"
            agg[key] += 1
            detail.setdefault(key, []).append(
                f"{fn}: {f['widget']} {f.get('layout','')} {f.get('side','')}"
            )

    print("=== AGGREGATE (kind=value : count) ===")
    for key, count in sorted(agg.items(), key=lambda kv: -kv[1]):
        print(f"  {key} : {count}")

    print("\n=== DETAIL (first 8 per key) ===")
    for key, items in sorted(detail.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[{key}] ({len(items)} total)")
        for it in items[:8]:
            print(f"  {it}")
        if len(items) > 8:
            print(f"  ... and {len(items) - 8} more")

    print(f"\nTotal findings: {sum(len(v) for v in all_findings.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
