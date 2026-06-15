import json
import logging
import os
import tempfile
import functools
from services.i18n import t

logger = logging.getLogger(__name__)

CONFIG_FILE = "data/company_config.json"

DEFAULT_CONFIG = {
    "company_name": t("invoice_pdf.default_company"),
    "cui": t("invoice_pdf.default_cui"),
    "reg_number": t("invoice_pdf.default_reg"),
    "address": t("invoice_pdf.default_address"),
    "phone": t("invoice_pdf.default_phone"),
    "email": t("invoice_pdf.default_email"),
    "logo_path": "",
    "company_color": "#6366f1",
    "signature_path": "",
    "stamp_path": "",
}


@functools.lru_cache(maxsize=1)
def load_company_config():
    if not os.path.exists(CONFIG_FILE):
        save_company_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.warning("Could not load company config, using defaults")
        return DEFAULT_CONFIG


def save_company_config(data):
    """Write company config atomically to prevent corruption on concurrent writes."""
    os.makedirs("data", exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir="data", suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, CONFIG_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    load_company_config.cache_clear()
