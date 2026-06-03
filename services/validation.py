import logging
import re
from services.i18n import t

logger = logging.getLogger(__name__)


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
        except Exception:
            logger.debug("Validation failed for km=%s price=%s", km, price)
            return False, t("validation.numeric_km_price")