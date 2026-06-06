from dataclasses import dataclass
from config import Config

@dataclass
class TripResult:
    net_profit: float
    fuel_cost: float
    toll_cost: float
    salary_cost: float
    extra_costs: float
    rate_per_km: float    # Profit Net / KM
    gross_per_km: float   # Venit Brut / KM
    margin_percent: float

class TripCalculator:
    @staticmethod
    def calculate(km, price_eur, fuel_price, days, consum_litri, extra_in, sal_in, taxa_in, fuel_cost_override=None):
        # 1. Salariu șofer (Automat 100€/zi dacă e 0)
        salary_cost = sal_in if sal_in > 0 else (days * Config.DEFAULT_DRIVER_SALARY)
        
        # 2. Taxe drum (Automat 0.22€/km dacă e 0)
        toll_cost = taxa_in if taxa_in > 0 else (km * Config.DEFAULT_TOLL_RATE)
        
        # 3. Costuri extra (Automat 0.03€/km + 12€/zi dacă e 0)
        if extra_in != 0:
            extra_costs = extra_in
        else:
            extra_costs = round((km * Config.EXTRA_COST_PER_KM) + (days * Config.EXTRA_COST_PER_DAY), 2)
        
        # 4. Consum combustibil
        # Use pre-calculated fuel cost from route planner if available
        if fuel_cost_override is not None and fuel_cost_override > 0:
            fuel_cost = fuel_cost_override
        else:
            fuel_cost = (km / 100) * consum_litri * fuel_price
        
        # 5. Calcule Finale
        total_costs = fuel_cost + toll_cost + salary_cost + extra_costs
        net_profit = price_eur - total_costs
        
        # Rate per kilometru
        rate_net_km = net_profit / km if km > 0 else 0
        rate_gross_km = price_eur / km if km > 0 else 0
        
        # Marja de profit
        margin = (net_profit / price_eur * 100) if price_eur > 0 else 0
        
        return TripResult(
            net_profit=round(net_profit, 2),
            fuel_cost=round(fuel_cost, 2),
            toll_cost=round(toll_cost, 2),
            salary_cost=round(salary_cost, 2),
            extra_costs=round(extra_costs, 2),
            rate_per_km=round(rate_net_km, 2),
            gross_per_km=round(rate_gross_km, 2),
            margin_percent=round(margin, 1)
        )