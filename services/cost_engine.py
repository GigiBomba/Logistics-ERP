import logging
from typing import Optional

from config import Config
from services.fuel_price_service import FuelPriceService

logger = logging.getLogger("cost_engine")


class CostEngineService:
    COUNTRY_FACTORS = {
        'RO': 1.0,
        'DE': 1.2,
        'FR': 1.3,
        'IT': 1.25,
        'DEFAULT': 1.0
    }

    ROAD_CLASS_FACTOR = {
        'motorway': 1.0,
        'trunk': 1.0,
        'primary': 0.8,
        'secondary': 0.5,
        'tertiary': 0.2,
        'default': 0.3
    }

    def __init__(self, fuel_price_eur_per_liter: Optional[float] = None, country_code: str = 'DEFAULT'):
        if fuel_price_eur_per_liter is not None:
            self._fixed_fuel_price = fuel_price_eur_per_liter
        else:
            self._fixed_fuel_price = None
        self._default_country = country_code

    @property
    def fuel_price(self) -> float:
        if self._fixed_fuel_price is not None:
            return self._fixed_fuel_price
        fuel_service = FuelPriceService()
        return fuel_service.get_price(self._default_country)

    def estimate(self, distance_km: float, truck: dict, route_details: Optional[dict] = None, country_code: str = 'DEFAULT') -> dict:
        if distance_km is None:
            return {
                'fuel_liters': 0.0,
                'fuel_cost': 0.0,
                'toll_cost': 0.0,
                'total_cost': 0.0
            }
        consumption = truck.get('fuel_consumption_l_per_100km') or truck.get('fuel_consumption') or 34.0
        fuel_liters = (distance_km / 100.0) * float(consumption)
        fuel_cost = fuel_liters * self.fuel_price

        country_factor = self.COUNTRY_FACTORS.get(country_code, self.COUNTRY_FACTORS['DEFAULT'])
        avg_road_factor = 0.5
        if route_details and 'road_class' in route_details:
            avg_road_factor = route_details.get('road_class', 0.5)

        toll_rate = Config.DEFAULT_TOLL_RATE
        toll_cost = distance_km * toll_rate * country_factor * avg_road_factor

        total = fuel_cost + toll_cost

        return {
            'fuel_liters': round(fuel_liters, 2),
            'fuel_cost': round(fuel_cost, 2),
            'toll_cost': round(toll_cost, 2),
            'total_cost': round(total, 2)
        }
