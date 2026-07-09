import functools
import json
import logging
import os
import tempfile

from services.i18n import t

logger = logging.getLogger(__name__)

from utils.resource_path import data_path

CONFIG_FILE = data_path("data/company_config.json")

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
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Company config is not a dict, using defaults")
            return dict(DEFAULT_CONFIG)
        missing = [k for k in DEFAULT_CONFIG if k not in data]
        if missing:
            logger.warning("Company config missing fields: %s, using defaults for those", missing)
            result = dict(DEFAULT_CONFIG)
            result.update(data)
            return result
        return data
    except Exception:
        logger.warning("Could not load company config, using defaults")
        return dict(DEFAULT_CONFIG)


def save_company_config(data):
    """Write company config atomically to prevent corruption on concurrent writes."""
    data_dir = os.path.dirname(CONFIG_FILE)
    os.makedirs(data_dir, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=data_dir, suffix=".json")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, CONFIG_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    finally:
        load_company_config.cache_clear()
