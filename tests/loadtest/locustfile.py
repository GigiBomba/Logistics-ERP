"""Locust load testing — main entry point.

Usage:
    locust --host=http://localhost:8000 --users=10 --spawn-rate=2 --run-time=60s
    locust --headless --host=http://localhost:8000 --users=10 --spawn-rate=2 --run-time=120s --csv=ci-load
"""
from locust import HttpUser, between

from tests.loadtest.scenarios.auth_scenarios import AuthTasks
from tests.loadtest.scenarios.crud_scenarios import CrudTasks
from tests.loadtest.scenarios.document_scenarios import DocumentTasks
from tests.loadtest.scenarios.invoice_scenarios import InvoiceTasks
from tests.loadtest.scenarios.mixed_scenarios import MixedTasks


class AuthenticatedUser(HttpUser):
    """Simulates a dispatcher doing daily tasks — mixed reads and writes."""
    wait_time = between(1, 5)
    tasks = {AuthTasks: 10, CrudTasks: 30, DocumentTasks: 20, InvoiceTasks: 10, MixedTasks: 30}


class ReadOnlyUser(HttpUser):
    """Simulates a dashboard viewer — only reads."""
    wait_time = between(2, 8)
    tasks = {CrudTasks.list_trips: 5, CrudTasks.list_clients: 3, CrudTasks.list_drivers: 2,
             CrudTasks.list_fleet: 2, CrudTasks.get_trip: 3, CrudTasks.get_client: 2}


class AdminUser(HttpUser):
    """Simulates an admin running reports and managing data."""
    wait_time = between(5, 15)
    tasks = {AuthTasks: 5, CrudTasks.list_all: 4, CrudTasks.create_trip: 2,
             CrudTasks.create_client: 2, MixedTasks.export_report: 2}
