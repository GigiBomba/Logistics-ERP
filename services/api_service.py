import logging

from services.exchange_rate_service import ExchangeRateService
from services.fuel_price_service import FuelPriceService

logger = logging.getLogger("api_service")


class APIService:
    def __init__(self):
        self._fuel_service = FuelPriceService()
        self._exchange_service = ExchangeRateService()

    def get_diesel_price(self, country_code: str = "DEFAULT") -> float:
        return self._fuel_service.get_price(country_code)

    def get_rates(self):
        return self._exchange_service.get_all_rates()

    def refresh_fuel_prices(self, background: bool = True) -> bool:
        return self._fuel_service.refresh(background)

    def refresh_exchange_rates(self, background: bool = True) -> bool:
        return self._exchange_service.refresh(background)
