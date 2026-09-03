"""Tests for Phase 4+6 insight jobs — §18.

Verifies each job runs without crashing and produces expected insight types.
"""
from __future__ import annotations


import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestInsightJobSignatures:
    """Insight job signatures and behavior."""

    def test_maintenance_forecast_job_exists(self):
        """maintenance_forecast_job Celery task must be importable."""
        from backend.celery_app.tasks.insight_tasks import maintenance_forecast_job
        assert maintenance_forecast_job is not None

    def test_overdue_invoice_job_exists(self):
        from backend.celery_app.tasks.insight_tasks import overdue_invoice_job
        assert overdue_invoice_job is not None

    def test_fleet_availability_job_exists(self):
        from backend.celery_app.tasks.insight_tasks import fleet_availability_job
        assert fleet_availability_job is not None

    def test_fuel_cost_trend_job_exists(self):
        from backend.celery_app.tasks.insight_tasks import fuel_cost_trend_job
        assert fuel_cost_trend_job is not None

    def test_return_load_matcher_job_exists(self):
        from backend.celery_app.tasks.insight_tasks import return_load_matcher_job
        assert return_load_matcher_job is not None

    def test_driver_hours_forecast_job_exists(self):
        from backend.celery_app.tasks.insight_tasks import driver_hours_forecast_job
        assert driver_hours_forecast_job is not None

    def test_generate_all_insights_dispatches_all_six(self):
        """generate_all_insights dispatches all 6 insight tasks.

        The Celery ``delay()`` call resolves through the shared Task base
        class, so patching ``celery.app.task.Task.delay`` intercepts all six
        dispatches without a broker.  (Patching ``type(task)`` does not work
        — Celery task modules export ``PromiseProxy`` objects.)
        """
        from unittest.mock import patch
        from celery.app.task import Task
        from backend.celery_app.tasks.insight_tasks import generate_all_insights
        
        with patch.object(Task, 'delay', return_value=MagicMock(id='mock')):
            result = generate_all_insights()
            assert len(result) == 6
            assert "maintenance" in result
            assert "overdue_invoices" in result
            assert "fleet_availability" in result
            assert "fuel_cost_trend" in result
            assert "return_load_matcher" in result
            assert "driver_hours_forecast" in result


class TestInsightJobTimeLimits:
    """Per-task time limits (approved performance fix).

    Each company-pass insight job gets a 15 min hard / 14 min soft limit so a
    single slow company pass cannot hold a worker for the global 30m/25m
    ceiling.  ``generate_all_insights`` gets 30 min / 29 min.  The pre-existing
    retry kwargs must be preserved.
    """

    ALL_SEVEN_JOBS = [
        "maintenance_forecast_job",
        "overdue_invoice_job",
        "fleet_availability_job",
        "fuel_cost_trend_job",
        "return_load_matcher_job",
        "driver_hours_forecast_job",
        "workflow_struggle_job",
    ]

    def test_all_seven_job_tasks_have_15_minute_time_limit(self):
        from backend.celery_app.tasks import insight_tasks
        for name in self.ALL_SEVEN_JOBS:
            task = getattr(insight_tasks, name)
            assert task.time_limit == 900, f"{name}.time_limit == 900"
            assert task.soft_time_limit == 840, f"{name}.soft_time_limit == 840"

    def test_job_tasks_keep_existing_retry_kwargs(self):
        from backend.celery_app.tasks import insight_tasks
        for name in self.ALL_SEVEN_JOBS:
            task = getattr(insight_tasks, name)
            assert task.max_retries == 2, f"{name}.max_retries == 2"
            assert task.default_retry_delay == 300, f"{name}.default_retry_delay == 300"

    def test_generate_all_insights_has_30_minute_time_limit(self):
        from backend.celery_app.tasks.insight_tasks import generate_all_insights
        assert generate_all_insights.time_limit == 1800
        assert generate_all_insights.soft_time_limit == 1740
