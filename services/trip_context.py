from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any, Dict
import uuid
import json
from datetime import datetime


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class RouteModel:
    start: Optional[Dict[str, Any]] = field(default_factory=lambda: {})
    stops: List[Dict[str, Any]] = field(default_factory=list)
    end: Optional[Dict[str, Any]] = field(default_factory=lambda: {})
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    profile: Optional[str] = None
    geometry: Optional[Any] = None
    route_history_v2_id: Optional[int] = None


@dataclass
class TruckModel:
    id: Optional[str] = None
    name: Optional[str] = None
    max_weight_kg: Optional[float] = None
    height_m: Optional[float] = None
    width_m: Optional[float] = None
    fuel_consumption_l_per_100km: Optional[float] = None


@dataclass
class DriverModel:
    id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class CostsModel:
    fuel_liters: Optional[float] = None
    fuel_cost: Optional[float] = None
    toll_cost: Optional[float] = None


@dataclass
class ProfitModel:
    revenue_estimate: Optional[float] = None
    total_cost: Optional[float] = None
    net_profit: Optional[float] = None


@dataclass
class TripContext:
    trip_id: str = field(default_factory=_new_id)
    route: RouteModel = field(default_factory=RouteModel)
    truck: TruckModel = field(default_factory=TruckModel)
    driver: DriverModel = field(default_factory=DriverModel)
    costs: CostsModel = field(default_factory=CostsModel)
    profit: ProfitModel = field(default_factory=ProfitModel)
    calculator_sync: bool = True
    status: str = 'draft'  # draft | active | saved

    # Helper initializer
    @classmethod
    def create(cls, trip_id: Optional[str] = None) -> 'TripContext':
        """Return a new TripContext with defaults. If trip_id provided it is used."""
        if trip_id:
            return cls(trip_id=trip_id)
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize TripContext to plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TripContext':
        """Create TripContext from plain dict. No computation performed; missing fields are tolerated."""
        tc = cls(trip_id=data.get('trip_id') or _new_id())

        rt = data.get('route') or {}
        tc.route = RouteModel(
            start=rt.get('start') or {},
            stops=rt.get('stops') or [],
            end=rt.get('end') or {},
            distance_km=rt.get('distance_km'),
            duration_min=rt.get('duration_min'),
            profile=rt.get('profile'),
            geometry=rt.get('geometry')
        )

        tr = data.get('truck') or {}
        tc.truck = TruckModel(
            id=tr.get('id'),
            name=tr.get('name'),
            max_weight_kg=tr.get('max_weight_kg'),
            height_m=tr.get('height_m'),
            width_m=tr.get('width_m'),
            fuel_consumption_l_per_100km=tr.get('fuel_consumption_l_per_100km')
        )

        dr = data.get('driver') or {}
        tc.driver = DriverModel(id=dr.get('id'), name=dr.get('name'))

        cs = data.get('costs') or {}
        tc.costs = CostsModel(
            fuel_liters=cs.get('fuel_liters'),
            fuel_cost=cs.get('fuel_cost'),
            toll_cost=cs.get('toll_cost')
        )

        pf = data.get('profit') or {}
        tc.profit = ProfitModel(
            revenue_estimate=pf.get('revenue_estimate'),
            total_cost=pf.get('total_cost'),
            net_profit=pf.get('net_profit')
        )

        tc.calculator_sync = bool(data.get('calculator_sync', True))
        tc.status = data.get('status', 'draft')
        return tc

    # Lightweight setters (no logic / no calculations)
    def set_route(self, route: Dict[str, Any]) -> None:
        self.route = RouteModel(
            start=route.get('start') or {},
            stops=route.get('stops') or [],
            end=route.get('end') or {},
            distance_km=route.get('distance_km'),
            duration_min=route.get('duration_min'),
            profile=route.get('profile'),
            geometry=route.get('geometry')
        )

    def set_truck(self, truck: Dict[str, Any]) -> None:
        self.truck = TruckModel(
            id=truck.get('id'),
            name=truck.get('name'),
            max_weight_kg=truck.get('max_weight_kg'),
            height_m=truck.get('height_m'),
            width_m=truck.get('width_m'),
            fuel_consumption_l_per_100km=truck.get('fuel_consumption_l_per_100km')
        )

    def set_driver(self, driver: Dict[str, Any]) -> None:
        self.driver = DriverModel(id=driver.get('id'), name=driver.get('name'))

    def set_costs(self, costs: Dict[str, Any]) -> None:
        self.costs = CostsModel(
            fuel_liters=costs.get('fuel_liters'),
            fuel_cost=costs.get('fuel_cost'),
            toll_cost=costs.get('toll_cost')
        )

    def set_profit(self, profit: Dict[str, Any]) -> None:
        self.profit = ProfitModel(
            revenue_estimate=profit.get('revenue_estimate'),
            total_cost=profit.get('total_cost'),
            net_profit=profit.get('net_profit')
        )

    def mark_saved(self) -> None:
        self.status = 'saved'

    def mark_active(self) -> None:
        self.status = 'active'

    def mark_draft(self) -> None:
        self.status = 'draft'


def update_trip_route(tc: TripContext, route: dict) -> TripContext:
    """Update TripContext.route with provided route dict.

    This function only mutates the TripContext instance and performs light validation
    of expected keys. No calculations, UI updates or DB writes are performed.
    """
    if not isinstance(route, dict):
        raise ValueError('route must be a dict')

    # Normalize keys minimally; accept missing fields
    tc.set_route({
        'start': route.get('start'),
        'stops': route.get('stops') or [],
        'end': route.get('end'),
        'distance_km': route.get('distance_km'),
        'duration_min': route.get('duration_min'),
        'geometry': route.get('geometry')
    })
    # Recompute costs when route changes
    try:
        _compute_costs_for_tc(tc)
    except Exception:
        pass
    _notify_listeners(tc, ['route', 'costs', 'profit'])
    return tc


def update_trip_truck(tc: TripContext, truck: dict) -> TripContext:
    """Update TripContext.truck with provided truck dict.

    Only updates data on the TripContext; no side effects.
    """
    if not isinstance(truck, dict):
        raise ValueError('truck must be a dict')

    tc.set_truck({
        'id': truck.get('id'),
        'name': truck.get('name'),
        'max_weight_kg': truck.get('max_weight_kg'),
        'height_m': truck.get('height_m'),
        'width_m': truck.get('width_m'),
        'fuel_consumption_l_per_100km': truck.get('fuel_consumption_l_per_100km')
    })
    # Recompute costs when truck changes
    try:
        _compute_costs_for_tc(tc)
    except Exception:
        pass
    _notify_listeners(tc, ['truck', 'costs', 'profit'])
    return tc


def update_trip_driver(tc: TripContext, driver: dict) -> TripContext:
    """Update TripContext.driver with provided driver dict.

    Only updates data on the TripContext; no side effects.
    """
    if not isinstance(driver, dict):
        raise ValueError('driver must be a dict')

    tc.set_driver({
        'id': driver.get('id'),
        'name': driver.get('name')
    })
    _notify_listeners(tc, ['driver'])
    return tc


# Observer registry for TripContext updates
_listeners = set()


def register_trip_listener(cb):
    """Register a callback to receive TripContext updates.

    Callback signature: cb(tc: TripContext, changed_fields: list)
    """
    try:
        _listeners.add(cb)
    except Exception:
        pass


def unregister_trip_listener(cb):
    try:
        _listeners.discard(cb)
    except Exception:
        pass


def _notify_listeners(tc: TripContext, changed_fields: list):
    for cb in list(_listeners):
        try:
            # Callbacks should be resilient; schedule via direct call (UI must handle threading)
            cb(tc, changed_fields)
        except Exception:
            # ignore listener errors
            pass


def _compute_costs_for_tc(tc: TripContext) -> None:
    """Compute basic costs and update tc.costs.

    Rules:
    - fuel_liters = (distance_km / 100) * truck.fuel_consumption_l_per_100km
    - fuel_cost = fuel_liters * FUEL_PRICE_PER_LITER (from FuelPriceService)
    - toll_cost = simple heuristic: distance_km * TOLL_PER_KM

    This function performs no UI or DB operations.
    """
    TOLL_PER_KM = 0.05  # placeholder toll per km

    try:
        dist = tc.route.distance_km if tc.route and tc.route.distance_km is not None else None
        fuel_consumption = tc.truck.fuel_consumption_l_per_100km if tc.truck and tc.truck.fuel_consumption_l_per_100km is not None else None

        if dist is None or fuel_consumption is None:
            tc.costs = CostsModel(fuel_liters=None, fuel_cost=None, toll_cost=None)
            return

        fuel_liters = (float(dist) / 100.0) * float(fuel_consumption)
        from services.fuel_price_service import FuelPriceService
        fuel_price = FuelPriceService().get_price("DEFAULT")
        fuel_cost = fuel_liters * fuel_price
        toll_cost = float(dist) * TOLL_PER_KM

        tc.costs = CostsModel(
            fuel_liters=round(fuel_liters, 3),
            fuel_cost=round(fuel_cost, 2),
            toll_cost=round(toll_cost, 2)
        )
    except Exception:
        return
    try:
        _compute_profit_for_tc(tc)
    except Exception:
        pass


def _compute_profit_for_tc(tc: TripContext) -> None:
    """Compute basic profit values and update tc.profit.

    Formula:
      total_cost = fuel_cost + toll_cost
      net_profit = revenue_estimate - total_cost

    This function updates profit fields when enough data is available.
    """
    try:
        rev = None
        try:
            rev = tc.profit.revenue_estimate
        except Exception:
            rev = None

        fuel_cost = tc.costs.fuel_cost if tc.costs and tc.costs.fuel_cost is not None else None
        toll_cost = tc.costs.toll_cost if tc.costs and tc.costs.toll_cost is not None else None

        if fuel_cost is None and toll_cost is None:
            # Nothing to compute
            tc.profit = ProfitModel(revenue_estimate=rev, total_cost=None, net_profit=None)
            return

        total_cost = 0.0
        if fuel_cost is not None:
            total_cost += float(fuel_cost)
        if toll_cost is not None:
            total_cost += float(toll_cost)

        if rev is None:
            # have total_cost but no revenue estimate
            tc.profit = ProfitModel(revenue_estimate=None, total_cost=round(total_cost, 2), net_profit=None)
            return

        # both revenue and costs available -> compute net profit
        net = float(rev) - total_cost
        tc.profit = ProfitModel(revenue_estimate=float(rev), total_cost=round(total_cost, 2), net_profit=round(net, 2))
    except Exception:
        # on error, do not raise
        return


def update_trip_revenue(tc: TripContext, revenue: Optional[float]) -> TripContext:
    """Update TripContext.profit.revenue_estimate and recompute profit.

    No side effects beyond TripContext mutation.
    """
    try:
        # allow None to unset
        if revenue is None:
            tc.profit.revenue_estimate = None
        else:
            tc.profit.revenue_estimate = float(revenue)
    except Exception:
        tc.profit.revenue_estimate = None

    try:
        _compute_profit_for_tc(tc)
    except Exception:
        pass
    _notify_listeners(tc, ['profit'])
    return tc


def save_trip_to_db(db_manager, tc: TripContext, client_name: Optional[str] = None) -> int:
    """Persist a TripContext snapshot into the trips table.

    Writes a single-row snapshot (including full context_json) in one transaction.
    Returns the database trip id.
    """
    if tc is None:
        raise ValueError("tc must be provided")

    # Prepare row payload - map TripContext fields to trips columns
    payload = {
        'created_at': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'truck_number': tc.truck.name if tc.truck and tc.truck.name else None,
        'driver_name': tc.driver.name if tc.driver and tc.driver.name else None,
        'client_name': client_name or None,
        'distance_km': tc.route.distance_km if tc.route and tc.route.distance_km is not None else None,
        'total_price_eur': tc.profit.revenue_estimate if tc.profit and tc.profit.revenue_estimate is not None else None,
        'rate_per_km': None,
        'gross_per_km': None,
        'net_profit': tc.profit.net_profit if tc.profit and tc.profit.net_profit is not None else None,
        'start_date': None,
        'end_date': None,
        'payment_date': None,
        'extra_costs': None,
        'fuel_cost': tc.costs.fuel_cost if tc.costs and tc.costs.fuel_cost is not None else None,
        'toll_cost': tc.costs.toll_cost if tc.costs and tc.costs.toll_cost is not None else None,
        'salary_cost': None,
        'currency': None,
        'status': tc.status or 'saved',
        'context_json': json.dumps(tc.to_dict(), default=str)
    }

    # Use db_manager.add_trip which already performs a single-transaction insert
    trip_db_id = db_manager.add_trip(payload)
    # notify listeners about saved trip
    try:
        tc.status = 'saved'
        _notify_listeners(tc, ['saved'])
    except Exception:
        pass
    return trip_db_id


def load_trip_from_db(db_manager, trip_db_id) -> Optional[TripContext]:
    """Load trip row by DB id and rebuild a TripContext.

    After rebuilding, notifies listeners so UI can refresh from TripContext.
    """
    row = db_manager.get_trip_by_id(trip_db_id)
    if not row:
        return None

    ctx_json = row.get('context_json')
    tc = None
    if ctx_json:
        try:
            data = json.loads(ctx_json)
            tc = TripContext.from_dict(data)
        except Exception:
            tc = None

    if tc is None:
        # Fallback: construct from available columns
        data = {
            'trip_id': _new_id(),
            'route': {
                'distance_km': row.get('distance_km'),
                'duration_min': None,
                'geometry': None,
            },
            'truck': {
                'name': row.get('truck_number')
            },
            'driver': {
                'name': row.get('driver_name')
            },
            'costs': {
                'fuel_cost': row.get('fuel_cost'),
                'toll_cost': row.get('toll_cost'),
            },
            'profit': {
                'revenue_estimate': row.get('total_price_eur'),
                'net_profit': row.get('net_profit'),
                'total_cost': None
            },
            'calculator_sync': True,
            'status': row.get('status', 'saved')
        }
        tc = TripContext.from_dict(data)

    # mark loaded as saved
    try:
        tc.status = row['status'] if 'status' in row.keys() and row['status'] else 'saved'
    except Exception:
        tc.status = 'saved'

    # Notify listeners so UI and calculator refresh from TripContext
    try:
        _notify_listeners(tc, ['load', 'route', 'truck', 'driver', 'costs', 'profit'])
    except Exception:
        pass

    return tc


class TripContextService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TripContextService, cls).__new__(cls)
            cls._instance._active_trip_info = {
                "distance_km": 0.0,
                "duration_min": 0.0,
                "fuel_liters": 0.0,
                "fuel_cost": 0.0,
                "cost_per_km": 0.0,
                "net_profit": 0.0
            }
            # maintain an internal TripContext instance to integrate with module listeners
            try:
                cls._instance._tc = TripContext.create()
            except Exception:
                cls._instance._tc = None
        return cls._instance

    def set_active_trip_info(
        self,
        distance_km: Optional[float] = None,
        duration_min: Optional[float] = None,
        fuel_liters: Optional[float] = None,
        fuel_cost: Optional[float] = None,
        cost_per_km: Optional[float] = None,
        net_profit: Optional[float] = None,
        route_history_v2_id: Optional[int] = None,
    ):
        # Merge provided values with existing ones to preserve manual overrides
        info = dict(self._active_trip_info)
        if distance_km is not None:
            info['distance_km'] = distance_km
        if duration_min is not None:
            info['duration_min'] = duration_min
        if fuel_liters is not None:
            info['fuel_liters'] = fuel_liters
        if fuel_cost is not None:
            info['fuel_cost'] = fuel_cost
        if cost_per_km is not None:
            info['cost_per_km'] = cost_per_km
        if net_profit is not None:
            info['net_profit'] = net_profit

        self._active_trip_info = info

        # Also update module TripContext and notify listeners for UI sync if available
        try:
            if getattr(self, '_tc', None) is None:
                self._tc = TripContext.create()
            # Update minimal route/truck/costs in TripContext
            route_update = {'distance_km': info.get('distance_km'), 'duration_min': info.get('duration_min'), 'geometry': None}
            if route_history_v2_id is not None:
                route_update['route_history_v2_id'] = route_history_v2_id
            update_trip_route(self._tc, route_update)
            costs_update = {'fuel_liters': info.get('fuel_liters'), 'fuel_cost': info.get('fuel_cost'), 'toll_cost': None}
            self._tc.set_costs(costs_update)
            _notify_listeners(self._tc, ['route', 'costs'])
        except Exception:
            # non-fatal: preserve active_trip_info even if TripContext update fails
            pass

    def get_active_trip_info(self) -> dict:
        return self._active_trip_info