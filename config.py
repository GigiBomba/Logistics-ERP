import os

class Config:
    APP_NAME = "Cashflow Manager v2.0 - Logistics"
    DB_PATH = "data/cashflow.db"
    LOG_FILE = "logs/app.log"
    REPORTS_DIR = "reports"
    
    # Valori implicite pentru calcule automate
    DEFAULT_DRIVER_SALARY = 100.0  # EUR/zi
    DEFAULT_TOLL_RATE = 0.22      # EUR/km
    EXTRA_COST_PER_KM = 0.03      # EUR/km
    EXTRA_COST_PER_DAY = 12.0     # EUR/zi
    
    # API URLs
    CURRENCY_API = "https://open.er-api.com/v6/latest/EUR"
    
    # Creare directoare necesare
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)