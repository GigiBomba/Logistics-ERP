import re
from services.i18n import t

class ValidationService:
    @staticmethod
    def sanitize(text):
        if not text: return ""
        return re.sub(r'[^\w\s\.-]', '', text).strip()

    @staticmethod
    def validate_trip_input(km, price):
        try:
            k = float(km)
            p = float(price)
            if k <= 0 or p <= 0: return False, t("validation.positive_km_price")
            return True, ""
        except:
            return False, t("validation.numeric_km_price")