# UI Bug Sweep — Fix Plan

## Executive Summary
A comprehensive bug sweep of the entire UI layer of the PySide6 logistics calculator application was performed. 10 explorer agents scanned all UI folders and found:
- 16 Critical issues (crash-causing)
- 49 High severity issues (memory leaks, logic bugs, thread safety)
- 42 Medium severity issues (silent failures, missing validation)
- 31 Low severity issues (code smells, accessibility)

## Batch 1 — Critical Crash Fixes (8 fixes, all independent)

### Fix 1: `display_type` called as callable
- **File**: `ui/dialogs/maintenance_view.py`, line 187
- **Issue**: `getattr(r, "display_type", lambda: "")()` — if `display_type` is a string, calling it raises `TypeError`
- **Fix**: Remove trailing `()` → `getattr(r, "display_type", "")`

### Fix 2: `None * 30` TypeError in interval_months
- **File**: `ui/dialogs/maintenance_view.py`, line 220
- **Issue**: `s.get('interval_months', '')*30` — if `interval_months` is None, `None * 30` raises TypeError
- **Fix**: `float(s.get('interval_months') or 0) * 30`

### Fix 3: `int("")` / `int(None)` ValueError in trip_picker
- **File**: `ui/dialogs/trip_picker_dialog.py`, line 147
- **Issue**: `int(trow.get("id") or 0)` — if id is empty string, `int("")` raises ValueError
- **Fix**: `int(str(trow.get("id", 0) or 0))`

### Fix 4: Missing key check in schedule editor
- **File**: `ui/views/automail/config_panel.py`, line 114
- **Issue**: `schedule["id"]` without checking if key exists
- **Fix**: `schedule.get("id")`

### Fix 5: Layout bug — profit_card added after parent
- **File**: `ui/views/client_workspace/client_details.py`, lines 229-234
- **Issue**: `cl.addWidget(row2)` at line 232 before `profit_card` is added to `row2_layout` at line 234
- **Fix**: Move `cl.addWidget(row2)` to after line 234

### Fix 6: `_revenue_tab.layout()` None crash
- **File**: `ui/views/client_workspace/client_workspace.py`, line 474
- **Issue**: `self._revenue_tab.layout().addWidget(...)` — layout() can return None
- **Fix**: Guard with `layout = self._revenue_tab.layout(); if layout: layout.addWidget(...)`

### Fix 7: Cross-thread GUI signal safety in login_dialog
- **File**: `ui/dialogs/login_dialog.py`, lines 334-336
- **Issue**: Worker signals may fire from non-main thread
- **Fix**: Use explicit `Qt.QueuedConnection` on all worker→dialog connections

### Fix 8: `_automail_repo` never initialized
- **File**: `ui/views/automail/timeline_panel.py`, lines 256, 321
- **Issue**: `self._automail_repo` referenced but never defined as attribute
- **Fix**: Add `self._automail_repo = None` in `__init__`

## Batch 2 — High-Severity Widget Lifecycle Fixes

### Fix 9: `trip_card` missing cleanup
- **File**: `ui/widgets/trip_card.py`
- **Issue**: `_dismiss_error()` doesn't remove widget from layout before deleteLater
- **Fix**: Add `self._content_widget.layout().removeWidget(self._error_lbl)` before `deleteLater()`

### Fix 10: `toast` animation double-start
- **File**: `ui/widgets/toast.py`, lines 54-64, 86-87
- **Issue**: `_start_fade_out()` can call `start()` on already-running animation
- **Fix**: Check `not self._fade_out.state() == QPropertyAnimation.Running` before starting

### Fix 11: `loading_overlay` double-delete
- **File**: `ui/widgets/loading_overlay.py`, lines 104-109
- **Issue**: `mark_done()` can be called twice due to race with safety timer
- **Fix**: Add `if self._finished: return` guard (already exists, verify it works)

### Fix 12: `async_task` blocking wait
- **File**: `ui/widgets/async_task.py`, lines 90-96
- **Issue**: `cancel()` calls `self._thread.wait(2000)` blocking GUI thread
- **Fix**: Use non-blocking pattern or reduce timeout with deferred cleanup

### Fix 13: `stat_card_row` clear doesn't remove from layout
- **File**: `ui/widgets/stat_card_row.py`, lines 51-54
- **Issue**: `card.deleteLater()` called without `self._layout.removeWidget(card)`
- **Fix**: Add `self._layout.removeWidget(card)` before `deleteLater()`

### Fix 14-16: Widget destroy() additions
- **Files**: `kanban_column.py`, `dispatch_timeline.py`, `service_timeline_widget.py`
- **Issue**: Missing `_clear_cards()` / `_clear()` / `_clear_scroll()` in destroy()
- **Fix**: Add cleanup calls as first line of destroy()

## Batch 3 — High-Severity Logic / Thread Safety

### Fix 17: Cross-thread dict access in board_state
- **File**: `ui/views/dispatch_board/board_state.py`, lines 60-64, 98, 102
- **Issue**: `_alert_counts` dict accessed from background and main threads without sync
- **Fix**: Use `QMutex` to guard concurrent access

### Fix 18: EventBus subscribe/unsubscribe mismatch
- **File**: `ui/views/route_planner_view.py`, lines 392-395, 1677-1680
- **Issue**: Creates new `EventBus()` instance for both subscribe and unsubscribe — different instances
- **Fix**: Use `shared_event_bus` from `services.operations.event_bus`

### Fix 19: `loadFinished` connected multiple times
- **File**: `ui/map/map_widget.py`, line 123
- **Issue**: Signal connected every time `_build_map()` is called
- **Fix**: Disconnect before connecting: `try: self.loadFinished.disconnect(...); except TypeError: pass`

### Fix 20: `worker_ready` connected after `start()`
- **File**: `ui/views/automation_view/automation_queue.py`, lines 134-136
- **Issue**: Signal connected after worker starts — may miss early emission
- **Fix**: Move connection to before `worker.start()`

### Fix 21: `_event_bus` undefined in invoice_editor
- **File**: `ui/views/invoice_editor/editor_form.py`
- **Issue**: `self._event_bus` may not be initialized if `super().__init__()` not called properly
- **Fix**: Verify `BaseView.__init__` is called; add explicit initialization if needed

### Fix 22: DSO sparkline uses wrong data
- **File**: `ui/views/analytics/financial_tab.py`, line 147
- **Issue**: DSO KPI card shows profit sparkline instead of DSO trend
- **Fix**: Compute actual DSO trend or remove sparkline from DSO card

### Fix 23: FIFO eviction in plotly_renderer
- **File**: `ui/plotly_renderer.py`, lines 792-801
- **Issue**: Eviction uses `id()` which can be reused after GC
- **Fix**: Use `collections.OrderedDict` for true LRU cache

### Fix 24: Proforma discount_type edge case
- **File**: `ui/views/proforma_editor/editor_form.py`
- **Issue**: `_discount_type` defaults to `""` which may cause incorrect discount calculation
- **Fix**: Add explicit "none" option handling

## Batch 4 — Medium Severity

### Fix 25: Wrong translation key in receipt_editor
- **File**: `ui/views/receipt_editor/editor_form.py`, line 279
- **Fix**: Replace `t("invoice.trip_list_format")` with receipt-specific key

### Fix 26: Incomplete signal connections in cmr_form
- **File**: `ui/views/cmr_form_view/cmr_form.py`, lines 178-187
- **Fix**: Add `currentIndexChanged` and `valueChanged` handlers

### Fix 27: alert_card_delegate sizeHint
- **File**: `ui/delegates/alert_card_delegate.py`, line 87
- **Fix**: Use minimum width: `max(option.rect.width(), 300)`

### Fix 28: update_truck missing truck_id
- **File**: `ui/views/dispatch_board/dispatch_board.py`, lines 539, 644
- **Fix**: `card.update_truck(trip.get("truck_number", ""), trip.get("truck_id"))`

## Batch 5 — Low Severity / Code Quality

### Fix 30-33: EventBus subscription cleanup audit
- **Files**: All editors, analytics
- **Fix**: Ensure all subscriptions tracked via `BaseView._subs`

### Fix 34: Analytics timer cleanup
- **File**: `ui/views/analytics/_tab_base.py`
- **Fix**: Ensure `cleanup()` stops all timers

## Execution Order
1. Batch 1 (Critical) — All 8 fixes in parallel, different files
2. Batch 2 (Widget Lifecycle) — All parallel, no dependencies on Batch 1
3. Batch 3 (Logic/Thread) — Some depend on Batch 1 verification
4. Batch 4 (Medium) — Independent
5. Batch 5 (Low) — Independent

## Risk Assessment
- **High Risk**: Adding locks to board_state.py could introduce deadlocks. Use QMutex, not threading.Lock.
- **High Risk**: route_planner EventBus fix changes event routing architecture. Verify all event publishers use shared_event_bus.
- **Medium Risk**: Discount type fixes may affect calculation logic. Test all discount scenarios.
- **Low Risk**: Widget lifecycle fixes are straightforward additions.
