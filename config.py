import os
from typing import Dict

from utils.resource_path import data_path


class Config:
    APP_NAME = "Operion ERP"
    DB_PATH = os.environ.get("OPERION_DB_PATH") or data_path("data/cashflow.db")
    LOG_FILE = os.environ.get("OPERION_LOGS_DIR") or data_path("logs") + "/app.log"
    REPORTS_DIR = os.environ.get("OPERION_REPORTS_DIR") or data_path("reports")

    # Default costs for automated calculations
    DEFAULT_DRIVER_SALARY = float(os.environ.get("OPERION_DEFAULT_DRIVER_SALARY", "100.0"))
    DEFAULT_TOLL_RATE = float(os.environ.get("OPERION_DEFAULT_TOLL_RATE", "0.22"))
    EXTRA_COST_PER_KM = float(os.environ.get("OPERION_EXTRA_COST_PER_KM", "0.03"))
    EXTRA_COST_PER_DAY = float(os.environ.get("OPERION_EXTRA_COST_PER_DAY", "12.0"))

    # External API endpoints (overridable via environment)
    CURRENCY_API_PRIMARY = os.environ.get(
        "OPERION_CURRENCY_API", "https://open.er-api.com/v6/latest/EUR"
    )
    CURRENCY_API_FALLBACK = os.environ.get(
        "OPERION_CURRENCY_API_FALLBACK", "https://api.frankfurter.dev/latest?from=EUR"
    )
    GRAPHHOPPER_URL = os.environ.get(
        "OPERION_GRAPHHOPPER_URL", "https://maps.operionerp.xyz"
    )
    NOMINATIM_URL = os.environ.get(
        "OPERION_NOMINATIM_URL", "https://nominatim.openstreetmap.org"
    )

    # SMTP defaults (overridable via environment or settings table)
    SMTP_SERVER = os.environ.get("OPERION_SMTP_SERVER", "")
    SMTP_PORT = int(os.environ.get("OPERION_SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("OPERION_SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("OPERION_SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("OPERION_SMTP_FROM", "") or SMTP_USER

    # GraphHopper route profile mapping (UI label -> GH profile name)
    GRAPHHOPPER_PROFILES: Dict[str, str] = {
        "Recommended": "truck",
        "Fastest": "truck_fast",
        "Cheapest": "truck_cheap",
        "Safest": "truck_safe",
        "Shortest": "truck_short",
    }

    @classmethod
    def ensure_dirs(cls):
        """Create required directories."""
        os.makedirs(data_path("data"), exist_ok=True)
        os.makedirs(data_path("logs"), exist_ok=True)
        os.makedirs(data_path("reports"), exist_ok=True)
        os.makedirs(data_path("reports/invoices"), exist_ok=True)
        os.makedirs(data_path("invoices"), exist_ok=True)
        os.makedirs(data_path("data/documents"), exist_ok=True)