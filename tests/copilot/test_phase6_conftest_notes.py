"""Conftest update notes for Phase 6 tests.

The following additions are needed in `tests/conftest.py` to support Phase 6 tests:

1. **Kill switch fixtures** — Provide a Redis mock with `copilot:kill_switch:platform`
   and `copilot:kill_switch:company:{id}` keys for kill switch tests.

2. **Celery task patches** — Autouse fixtures to patch Celery `delay()` calls so insight
   task tests don't require a running Celery worker. Example:
   ```python
   @pytest.fixture(autouse=True)
   def patch_celery_delay(monkeypatch):
       monkeypatch.setattr(
           "backend.celery_app.tasks.insight_tasks.maintenance_forecast_job.delay",
           MagicMock(return_value=None),
       )
   ```

3. **Correlation context cleanup** — An autouse fixture to reset telemetry context
   between tests:
   ```python
   @pytest.fixture(autouse=True)
   def reset_telemetry_context():
       from backend.copilot.telemetry import (
           current_conversation_id, current_company_id, current_user_id,
       )
       current_conversation_id.set(None)
       current_company_id.set(None)
       current_user_id.set(None)
   ```

4. **Async event loop** — Ensure `pytest-asyncio` event_loop fixture is available:
   ```python
   @pytest.fixture(scope="session")
   def event_loop():
       import asyncio
       loop = asyncio.new_event_loop()
       yield loop
       loop.close()
   ```
"""
from __future__ import annotations

