"""Verify the analytics sparkline render fix across all 6 tabs.

Launches the real app (populated, offscreen), switches to Analytics, iterates
each of the 6 tabs, pumps the event loop to let async sparkline renders
complete, and reports how many ``_SparklineLabel`` instances have a non-null
pixmap (i.e. actually rendered) per tab.

Usage:
    python tools/verify_sparklines.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

TAB_NAMES = ["Financial", "Fleet", "Route", "Client", "Driver", "Document"]


def pump(app, ms: int) -> None:
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tab", type=int, default=None,
                        help="Verify only this tab index (0-5); default all.")
    args = parser.parse_args()

    db_path = os.path.join(
        tempfile.gettempdir(), f"ui_audit_spark_{os.getpid()}.db"
    )
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["OPERION_DB_PATH"] = db_path

    from utils.webengine_flags import apply_webengine_flags
    apply_webengine_flags()

    # Seed a populated DB.
    from database.db_manager import DatabaseManager
    db = DatabaseManager(db_path)
    db.conn.execute(
        "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
        "VALUES (1, 'Audit Co', 'starter')"
    )
    db.conn.commit()
    try:
        from tests.mobile.conftest import seed_records, seed_finance, seed_team
        seed_records(db, company_id=1)
        seed_finance(db, company_id=1)
        seed_team(db, company_id=1)
    except Exception as exc:
        print(f"WARNING: seeding partial ({exc})")
    db.close()

    # Auth bypass + disable tour/sync/chart-export (same as harness).
    payload = {"sub": "audit@test.local", "role": "admin", "exp": time.time() + 86400}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    from client.auth import Auth
    from client.auth_manager import set_auth
    set_auth(Auth(token="eyJhbGciOiJIUzI1NiJ9." + body + ".fake_sig"))

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
    try:
        import ui.plotly_renderer as _pr
        _pr.figure_to_svg_bytes = lambda fig, width=700, height=300, scale=1.0: (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width*scale)}" '
            f'height="{int(height*scale)}"><rect width="100%" height="100%" '
            f'fill="#141416"/></svg>'
        ).encode()
        import utils.chart_export as _ce
        _ce.configure_choreographer_export = lambda *a, **k: None
        _ce.shutdown_browser_sync = lambda *a, **k: None
    except Exception:
        pass
    try:
        import ui.copilot.controllers.struggle_detector as _sd
        _sd.StruggleDetector._trigger_nudge = lambda *a, **k: None
    except Exception:
        pass
    try:
        import ui.views.route_planner_view as _rp
        _rp.QtRoutePlannerView._lazy_init_map = lambda *a, **k: None
        import ui.views.fleet_tracking_view as _ft
        _ft.QtFleetTrackingView._build_map = lambda *a, **k: None
        import ui.views.route_history_view as _rh
        _rh.QtRouteHistoryView._create_map_widget = lambda *a, **k: None
    except Exception:
        pass

    from main import run_app
    result = run_app(return_window=True)
    if not (isinstance(result, tuple) and len(result) == 2):
        print(f"FATAL: run_app() did not return (app, window); got {result!r}")
        return 1
    app, window = result
    window.resize(1440, 900)
    window.show()
    pump(app, 2500)

    from PySide6.QtWidgets import QTabWidget
    from ui.views.analytics._tab_base import _SparklineLabel

    window._switch_module("analytics")
    pump(app, 2000)

    view = window._module_cache.get("analytics", {}).get("obj")
    if view is None:
        print("FATAL: analytics view not found")
        return 1

    tabs = view.findChildren(QTabWidget)
    if not tabs:
        print("FATAL: no QTabWidget found in analytics view")
        return 1
    tab_widget = tabs[0]

    print(f"Analytics tabs: {tab_widget.count()}", flush=True)
    all_ok = True
    indices = [args.tab] if args.tab is not None else list(range(tab_widget.count()))
    for i in indices:
        tab_widget.setCurrentIndex(i)
        pump(app, 2500)  # let async sparkline renders complete
        labels = view.findChildren(_SparklineLabel)
        rendered = [lbl for lbl in labels if lbl.pixmap() is not None and not lbl.pixmap().isNull()]
        name = TAB_NAMES[i] if i < len(TAB_NAMES) else f"tab{i}"
        status = "OK" if rendered and len(rendered) == len(labels) else "PARTIAL/FAIL"
        if status != "OK":
            all_ok = False
        print(f"  {name}: {len(rendered)}/{len(labels)} sparklines rendered [{status}]", flush=True)

    print(f"\nSparkline verification: {'PASS' if all_ok else 'FAIL'}", flush=True)
    os._exit(0 if all_ok else 1)


if __name__ == "__main__":
    sys.exit(main())
