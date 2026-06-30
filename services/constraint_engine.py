# services/constraint_engine.py
# Refactored: Improved parameter building for GraphHopper truck routing

from typing import Any, Optional

class TruckConstraintEngine:
    """
    Builds and validates truck constraints for GraphHopper routing.

    Supports all GraphHopper 11 truck routing parameters:
    - weight: Maximum weight in kg
    - height: Vehicle height in meters
    - width: Vehicle width in meters
    - length: Vehicle length in meters
    - axleload: Maximum axle load in kg
    - hazmat: Hazardous materials flag
    """

    # Default constraints
    MIN_CLEARANCE_M = 4.0
    MAX_WEIGHT_KG = 40000  # Standard EU truck max weight
    MAX_WIDTH_M = 2.55     # Standard EU truck max width
    MAX_HEIGHT_M = 4.0     # Standard EU max height
    MAX_LENGTH_M = 16.5    # Standard EU truck+trailer max length

    def __init__(self):
        self.logger = None
        try:
            from utils.logger import get_logger
            self.logger = get_logger("TruckConstraintEngine")
        except Exception:
            pass

    def validate_truck(self, truck: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate truck basic constraints.

        Args:
            truck: Truck configuration dict

        Returns:
            Tuple of (is_valid, message)
        """
        if not truck:
            return False, "No truck provided"

        # Check height
        height = self._get_truck_value(truck, 'height_m')
        if height is not None:
            try:
                h = float(height)
                if h > self.MIN_CLEARANCE_M:
                    return True, f"Truck height ({h}m) requires route clearance"
                if h > self.MAX_HEIGHT_M:
                    return False, f"Truck height ({h}m) exceeds maximum ({self.MAX_HEIGHT_M}m)"
            except (TypeError, ValueError):
                pass

        # Check weight
        weight = self._get_truck_value(truck, 'max_weight_kg') or self._get_truck_value(truck, 'weight_kg')
        if weight is not None:
            try:
                w = float(weight)
                if w > self.MAX_WEIGHT_KG:
                    return False, f"Truck weight ({w}kg) exceeds maximum ({self.MAX_WEIGHT_KG}kg)"
            except (TypeError, ValueError):
                pass

        # Check width
        width = self._get_truck_value(truck, 'width_m')
        if width is not None:
            try:
                w = float(width)
                if w > self.MAX_WIDTH_M:
                    return False, f"Truck width ({w}m) exceeds maximum ({self.MAX_WIDTH_M}m)"
            except (TypeError, ValueError):
                pass

        return True, "OK"

    def build_params(
        self,
        truck: dict[str, Any],
        profile: str = "truck"
    ) -> dict[str, str]:
        """
        Build GraphHopper truck routing parameters.

        Only includes valid, supported parameters for GraphHopper 11.
        Does NOT send unsupported params like mode_hint.

        Args:
            truck: Truck configuration dict
            profile: Routing profile name (for logging)

        Returns:
            Dict of GraphHopper query parameters
        """
        params = {}

        if not truck:
            return params

        try:
            # Weight (kg)
            weight = self._get_truck_value(truck, 'max_weight_kg') or self._get_truck_value(truck, 'weight_kg')
            if weight:
                w = float(weight)
                if 0 < w <= self.MAX_WEIGHT_KG:
                    params['weight'] = str(w)
                    if self.logger:
                        self.logger.debug(f"Truck weight: {w}kg")

            # Height (m)
            height = self._get_truck_value(truck, 'height_m')
            if height:
                h = float(height)
                if 0 < h <= self.MAX_HEIGHT_M:
                    params['height'] = str(h)
                    if self.logger:
                        self.logger.debug(f"Truck height: {h}m")

            # Width (m)
            width = self._get_truck_value(truck, 'width_m')
            if width:
                w = float(width)
                if 0 < w <= self.MAX_WIDTH_M:
                    params['width'] = str(w)
                    if self.logger:
                        self.logger.debug(f"Truck width: {w}m")

            # Length (m) - optional
            length = self._get_truck_value(truck, 'length_m')
            if length:
                length_val = float(length)
                if 0 < length_val <= self.MAX_LENGTH_M:
                    params['length'] = str(length_val)
                    if self.logger:
                        self.logger.debug(f"Truck length: {length_val}m")

            # Axle load (kg) - optional
            axleload = self._get_truck_value(truck, 'axleload_kg')
            if axleload:
                a = float(axleload)
                if a > 0:
                    params['axleload'] = str(a)
                    if self.logger:
                        self.logger.debug(f"Truck axleload: {a}kg")

            # Hazardous materials - optional
            hazmat = self._get_truck_value(truck, 'hazmat')
            if hazmat is not None:
                if isinstance(hazmat, bool):
                    params['hazmat'] = str(hazmat).lower()
                elif isinstance(hazmat, str):
                    params['hazmat'] = hazmat.lower() in ('true', 'yes', '1')
                    if self.logger:
                        self.logger.debug(f"Truck hazmat: {params['hazmat']}")

            if self.logger and params:
                self.logger.info(f"Built {len(params)} truck params for profile={profile}")

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to build some truck params: {e}")

        return params

    @staticmethod
    def _get_truck_value(truck: dict[str, Any], key: str) -> Optional[Any]:
        """Safely get value from truck dict"""
        try:
            # If it's a real dict-like object with get(), use it
            if hasattr(truck, 'get'):
                return truck.get(key)

            # Try mapping access (sqlite3.Row supports __getitem__ by column name)
            try:
                return truck[key]
            except Exception:
                # Fallback to attribute access if object exposes attributes
                return getattr(truck, key, None)
        except Exception:
            return None

    @staticmethod
    def validate_profile(profile: str) -> bool:
        """Validate GraphHopper profile name"""
        valid_profiles = {
            'truck', 'truck_fast', 'truck_safe',
            'truck_cheap', 'truck_short',
            'car', 'bike', 'foot'
        }
        return profile.lower() in valid_profiles
