import json
import os
from services.i18n import t

CONFIG_FILE = "data/company_config.json"

DEFAULT_CONFIG = {
    "company_name": t("invoice_pdf.default_company"),
    "cui": t("invoice_pdf.default_cui"),
    "reg_number": t("invoice_pdf.default_reg"),
    "address": t("invoice_pdf.default_address"),
    "phone": t("invoice_pdf.default_phone"),
    "email": t("invoice_pdf.default_email")
}

def load_company_config():
    if not os.path.exists(CONFIG_FILE):
        save_company_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG

def save_company_config(data):
    os.makedirs("data", exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
