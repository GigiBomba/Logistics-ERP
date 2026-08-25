"""Render-and-capture visual audit harness for the Operion PySide6 desktop ERP.

Usage
-----
    python tools/ui_audit_harness.py --seed
    python tools/ui_audit_harness.py --out tools/evidence --size 1024x600
    python tools/ui_audit_harness.py --pages overview,analytics --wait 800

The harness boots the real desktop app headlessly
(``QT_QPA_PLATFORM=offscreen``), switches through every stacked page of the
main window, and for each page saves:

    <key>_<state>.png          full-window screenshot
    <key>_<state>_view.png     screenshot of the page view widget only
    <key>_<state>.json         compact widget/layout geometry dump
    <key>_<state>.error.txt    traceback when a page raises (audit continues)

``--seed`` populates a throwaway temp SQLite database with the mobile test-suite
seed helpers so pages render in their *populated* state; without it the app
creates the schema on its own in an empty database (the *empty* state).

Environment contract (order matters, mirrors ``main.py``):
    1. ``QT_QPA_PLATFORM`` and ``OPERION_DB_PATH`` are set before anything else.
    2. ``utils.webengine_flags.apply_webengine_flags()`` runs before any
       PySide6 import (same as the top of ``main.py``).
    3. A fake admin JWT bypasses the admin login gate via ``set_auth``.
    4. Only then is ``main.run_app(return_window=True)`` imported and launched.

Exit code is 0 when every audited page captured OK, 1 otherwise.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import tempfile
import time
import traceback

# The app logs non-ASCII characters (e.g. arrows) that crash the default
# cp1252 console encoding on Windows; force UTF-8 with lossy fallback.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# The project root is the parent of this tools/ directory; make absolute
# imports (main, client.*, database.*, tests.*) resolvable regardless of
# the cwd the user launches the harness from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# All stacked page keys understood by MainWindow._switch_module.
ALL_PAGES = [
    "overview", "analytics", "route_planner", "calculator",
    "dispatch_board", "tracking", "freight_exchange", "fleet",
    "driver_manager", "clients", "documents", "maintenance",
    "maintenance_control", "tachograph", "invoices", "history",
    "route_history", "copilot", "migration_center", "settings", "team",
]

# Keep the geometry dumps compact — hard cap on recorded widgets per page.
MAX_WIDGETS = 400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render-and-capture audit harness for the Operion PySide6 ERP."
    )
    parser.add_argument(
        "--out", default="tools/evidence",
        help="Output directory for screenshots + geometry dumps "
             "(default: tools/evidence, created if missing).",
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="Populate the temp DB with the mobile test-suite seed helpers "
             "(populated state). Without it the DB stays empty (empty state).",
    )
    parser.add_argument(
        "--size", default="1440x900",
        help="Window size as WxH (default: 1440x900; try 1024x600 for "
             "minimum-size testing).",
    )
    parser.add_argument(
        "--pages", default=None,
        help="Comma-separated page keys to audit (default: all 21 stacked pages).",
    )
    parser.add_argument(
        "--wait", type=int, default=1500,
        help="Milliseconds to pump the Qt event loop after each page switch "
             "(default: 1500).",
    )
    parser.add_argument(
        "--collapse-sidebar", action="store_true",
        help="Collapse the sidebar to its 48px state before capturing "
             "(for responsive/truncation checks).",
    )
    return parser.parse_args()


def parse_size(size_str: str) -> tuple[int, int]:
    try:
        width, height = size_str.lower().split("x")
        return int(width), int(height)
    except Exception:
        raise SystemExit(f"Invalid --size {size_str!r}; expected WxH, e.g. 1440x900")


def pump(app, ms: int) -> None:
    """Pump the Qt event loop for *ms* milliseconds."""
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)


def build_fake_admin_token() -> str:
    """Fake HS256-shaped JWT carrying ``role: admin`` (signature ignored)."""
    payload = {
        "sub": "audit@test.local",
        "role": "admin",
        "exp": time.time() + 86400,
    }
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip("=")
    return "eyJhbGciOiJIUzI1NiJ9." + body + ".fake_sig"


def set_admin_auth() -> None:
    """Bypass the admin login gate by seeding the auth manager first."""
    from client.auth import Auth
    from client.auth_manager import set_auth

    set_auth(Auth(token=build_fake_admin_token()))


def seed_database(db_path: str) -> None:
    """Populate *db_path* using the mobile test-suite seed helpers.

    Each helper is isolated in its own try/except so one failure (e.g. an
    InvoiceService import problem in ``seed_finance``) does not abort the
    run — the app still launches against whatever got seeded.
    """
    from database.db_manager import DatabaseManager

    print(f"Seeding database: {db_path}")
    db = DatabaseManager(db_path)
    try:
        db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (1, 'Audit Co', 'starter')"
        )
        db.conn.commit()
        print("  OK company id=1")
    except Exception:
        print("  ERROR company id=1 (continuing anyway):")
        print("  " + traceback.format_exc().strip().replace("\n", "\n  "))

    try:
        from tests.mobile.conftest import (
            seed_company_settings,
            seed_finance,
            seed_records,
            seed_team,
        )
    except Exception as exc:
        print(f"  ERROR importing seed helpers: {exc}")
        try:
            db.close()
        except Exception:
            pass
        return

    helpers = (
        ("seed_records", seed_records),
        ("seed_finance", seed_finance),
        ("seed_team", seed_team),
        ("seed_company_settings", seed_company_settings),
    )
    for name, fn in helpers:
        try:
            fn(db, company_id=1)
            print(f"  OK {name}")
        except Exception:
            print(f"  ERROR {name} (continuing anyway):")
            print("  " + traceback.format_exc().strip().replace("\n", "\n  "))

    try:
        db.close()
    except Exception:
        pass


def collect_widget_info(root) -> list[dict]:
    """Walk *root*'s widget tree and dump compact geometry/layout facts.

    Records: class name, objectName, geometry rect, size hint, font
    point/pixel size, and for every layout on each widget its spacing and
    contents margins.  Skips widgets that are anonymous AND still at the
    default (0, 0, 0, 0) geometry; caps output at MAX_WIDGETS.
    """
    from PySide6.QtWidgets import QLayout, QWidget

    records: list[dict] = []
    widgets = [root] + list(root.findChildren(QWidget))
    for widget in widgets:
        rect = widget.geometry().getRect()
        if not widget.objectName() and tuple(rect) == (0, 0, 0, 0):
            continue  # anonymous + unpainted — noise, not signal

        entry = {
            "class": widget.__class__.__name__,
            "objectName": widget.objectName(),
            "geometry": list(rect),
            "sizeHint": [widget.sizeHint().width(), widget.sizeHint().height()],
            "font": {
                "pointSize": widget.font().pointSize(),
                "pixelSize": widget.font().pixelSize(),
            },
            "layouts": [],
        }

        layouts: list = []
        # Some widgets (e.g. ScrollableFormContainer in ui/widgets/__init__.py)
        # shadow Qt's layout() method with a plain instance attribute holding a
        # QLayout. Guard against that so one odd widget can't kill the dump.
        layout_attr = getattr(widget, "layout", None)
        if callable(layout_attr) and not isinstance(layout_attr, QLayout):
            try:
                top_layout = layout_attr()
            except Exception:
                top_layout = None
        else:
            top_layout = None
        if top_layout is not None:
            layouts.append(top_layout)
            try:
                layouts.extend(top_layout.findChildren(QLayout))
            except Exception:
                pass
        for layout in layouts:
            try:
                margins = layout.contentsMargins()
                entry["layouts"].append(
                    {
                        "class": layout.__class__.__name__,
                        "objectName": layout.objectName(),
                        "spacing": layout.spacing(),
                        "contentsMargins": [
                            margins.left(), margins.top(),
                            margins.right(), margins.bottom(),
                        ],
                    }
                )
            except Exception:
                continue

        records.append(entry)
        if len(records) >= MAX_WIDGETS:
            break
    return records


def capture_page(app, window, key: str, out_dir: str, state: str, wait_ms: int) -> bool:
    """Switch to *key*, pump events, then save screenshots + geometry dump.

    Any exception (view construction crash, unknown key, grab failure) is
    written to ``{key}_{state}.error.txt`` and swallowed; the audit moves on.
    """
    try:
        window._switch_module(key)
        pump(app, wait_ms)

        # The cached page object is ``{"frame": <widget>, "obj": <view>}``.
        view = None
        cache_entry = getattr(window, "_module_cache", {}).get(key)
        if isinstance(cache_entry, dict):
            view = cache_entry.get("obj")

        window_shot = os.path.join(out_dir, f"{key}_{state}.png")
        if not window.grab().save(window_shot):
            raise RuntimeError(f"window.grab().save() returned False for {window_shot}")

        if view is not None:
            view_shot = os.path.join(out_dir, f"{key}_{state}_view.png")
            if not view.grab().save(view_shot):
                raise RuntimeError(f"view.grab().save() returned False for {view_shot}")

        dump_path = os.path.join(out_dir, f"{key}_{state}.json")
        with open(dump_path, "w", encoding="utf-8") as fh:
            json.dump(
                collect_widget_info(view if view is not None else window),
                fh, indent=1,
            )
        return True
    except Exception:
        error_path = os.path.join(out_dir, f"{key}_{state}.error.txt")
        with open(error_path, "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        return False


def main() -> int:
    args = parse_args()
    state = "populated" if args.seed else "empty"
    width, height = parse_size(args.size)
    pages = [p.strip() for p in args.pages.split(",") if p.strip()] \
        if args.pages else list(ALL_PAGES)

    os.makedirs(args.out, exist_ok=True)

    # 1. Environment first — fresh temp DB per run. Include the PID so
    #    parallel harness processes don't clobber each other's database.
    db_path = os.path.join(
        tempfile.gettempdir(), f"ui_audit_{state}_{os.getpid()}.db"
    )
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["OPERION_DB_PATH"] = db_path

    print(f"Operion UI audit — state={state} size={width}x{height} pages={len(pages)}")
    print(f"DB: {db_path}")
    print(f"Output: {os.path.abspath(args.out)}")

    # 2. WebEngine flags before any PySide6 import (same as main.py).
    from utils.webengine_flags import apply_webengine_flags
    apply_webengine_flags()

    # 3. Optional seeding (empty state skips this entirely).
    if args.seed:
        seed_database(db_path)

    # 4. Bypass the admin login gate, then launch the real app.
    set_admin_auth()

    # Disable the onboarding tour (its guided overlay would cover every
    # screenshot) and the background sync engine (network noise + a worker
    # thread that would keep the process alive after capture). Both are
    # monkeypatched in-process only — no files or settings are touched.
    try:
        from ui.copilot import tour_tracker
        tour_tracker.is_tour_completed = lambda *a, **k: True
    except Exception:
        pass
    try:
        import main as _main
        _main.setup_sync = lambda *a, **k: None
    except Exception:
        pass

    # Stub the plotly SVG renderer: with real data it renders charts through a
    # headless Chrome browser that hangs for 60s+ per chart under offscreen Qt.
    # Return a minimal placeholder SVG instead so pages render with their full
    # layout intact (charts show as empty panels) without blocking the sweep.
    try:
        import ui.plotly_renderer as _pr

        def _placeholder_svg(fig, width=700, height=300, scale=1.0):
            w = max(1, int(width * scale))
            h = max(1, int(height * scale))
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                f'<rect width="100%" height="100%" fill="#141416"/></svg>'
            ).encode("utf-8")

        _pr.figure_to_svg_bytes = _placeholder_svg
        try:
            import utils.chart_export as _ce
            _ce.generate_svg_bytes_sync = lambda *a, **k: _placeholder_svg(
                a[0] if a else None, 700, 300, 1.0
            )
            # main.py calls configure_choreographer_export() at startup, which
            # eagerly launches a headless Chrome browser that hangs under
            # offscreen Qt. Neutralize it (and its shutdown hook) entirely.
            _ce.configure_choreographer_export = lambda *a, **k: None
            _ce.shutdown_browser_sync = lambda *a, **k: None
        except Exception:
            pass
        # The struggle detector shows a full-screen nudge overlay that blocks
        # page captures. Neutralize it at the source (the emit path).
        try:
            import ui.copilot.controllers.struggle_detector as _sd
            _sd.StruggleDetector._trigger_nudge = lambda *a, **k: None
        except Exception:
            pass
        # MapWidget loads a Folium map in QWebEngineView; under offscreen Qt the
        # Chromium process blocks the event loop when switching away. Skip map
        # creation entirely so the placeholder area renders instead.
        try:
            import ui.views.route_planner_view as _rp
            _rp.QtRoutePlannerView._lazy_init_map = lambda *a, **k: None
        except Exception:
            pass
        try:
            import ui.views.fleet_tracking_view as _ft
            _ft.QtFleetTrackingView._build_map = lambda *a, **k: None
        except Exception:
            pass
        try:
            import ui.views.route_history_view as _rh
            _rh.QtRouteHistoryView._create_map_widget = lambda *a, **k: None
        except Exception:
            pass
    except Exception:
        pass

    from main import run_app

    result = run_app(return_window=True)
    if not (isinstance(result, tuple) and len(result) == 2):
        print(f"FATAL: run_app() did not return (app, window); got {result!r}")
        return 1
    app, window = result

    window.resize(width, height)
    window.show()
    pump(app, 1500)

    # Optional: collapse the sidebar to its 48px state for responsive checks.
    if args.collapse_sidebar:
        try:
            from ui.widgets.sidebar import SIDEBAR_COLLAPSED
            window.app_shell.nav._set_width_immediate(SIDEBAR_COLLAPSED)
            pump(app, 400)
            print("Sidebar collapsed to 48px")
        except Exception:
            print("WARNING: could not collapse sidebar")

    # 5. Capture every requested page.
    results: dict[str, bool] = {}
    for key in pages:
        results[key] = capture_page(app, window, key, args.out, state, args.wait)
        print(f"  {key}: {'OK' if results[key] else 'ERROR'}")

    total = len(results)
    ok_count = sum(1 for ok in results.values() if ok)
    error_count = total - ok_count
    print(f"\nAudit complete: {total} pages, {ok_count} OK, {error_count} ERROR")
    print(f"Evidence written to: {os.path.abspath(args.out)}")
    # The app spawns background threads (worker pool, chart browser, timers)
    # that keep the process alive after capture. This is a headless capture
    # tool — hard-exit to terminate cleanly instead of hanging.
    os._exit(1 if error_count else 0)


if __name__ == "__main__":
    sys.exit(main())
