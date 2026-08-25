"""Integration health check service — monitors external API connectivity."""
from __future__ import annotations

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntegrationStatus:
    name: str
    connected: bool
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    latency_ms: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


class IntegrationHealthService:
    """Monitors and reports health of registered external integrations."""
    
    _REGISTERED_INTEGRATIONS = {
        "graphhopper": {
            "display_name": "GraphHopper Routing",
            "config_key_base": "graphhopper",
            "check_endpoint": "/health",  # or /status
        },
        "nominatim": {
            "display_name": "Nominatim Geocoding",
            "config_key_base": "nominatim",
            "check_endpoint": "/status",
        },
        "currency_api": {
            "display_name": "Exchange Rate API",
            "config_key_base": "currency_api",
            "check_endpoint": None,  # check via service method
        },
        "fuel_price": {
            "display_name": "Fuel Price Scraper",
            "config_key_base": "fuel_price",
            "check_endpoint": None,
        },
        "timocom": {
            "display_name": "TIMOCOM Freight Exchange",
            "config_key_base": "timocom",
            "check_endpoint": "/api/health",  # Placeholder for TIMOCOM
        },
    }
    
    def __init__(self, db):
        self.db = db
        self._status_cache: Dict[str, IntegrationStatus] = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def get_all_statuses(self) -> Dict[str, Any]:
        """Return status for all registered integrations."""
        results = {}
        for name in self._REGISTERED_INTEGRATIONS:
            results[name] = self.get_status(name)
        return {
            "integrations": results,
            "healthy_count": sum(1 for r in results.values() if r.get("connected", False)),
            "total_count": len(results),
        }
    
    def get_status(self, integration_name: str) -> Dict[str, Any]:
        """Get status for a specific integration."""
        info = self._REGISTERED_INTEGRATIONS.get(integration_name)
        if not info:
            return {"name": integration_name, "connected": False, "error": "Unknown integration"}
        
        # Check cache
        if integration_name in self._status_cache:
            cached = self._status_cache[integration_name]
            if cached.last_check and (datetime.now() - cached.last_check) < self._cache_ttl:
                return _status_to_dict(cached)
        
        # Check connectivity
        status = self._check_integration(integration_name, info)
        self._status_cache[integration_name] = status
        return _status_to_dict(status)
    
    def check_now(self, integration_name: str) -> Dict[str, Any]:
        """Force an immediate health check."""
        info = self._REGISTERED_INTEGRATIONS.get(integration_name)
        if not info:
            return {"name": integration_name, "connected": False, "error": "Unknown integration"}
        status = self._check_integration(integration_name, info)
        self._status_cache[integration_name] = status
        return _status_to_dict(status)
    
    def _check_integration(self, name: str, info: dict) -> IntegrationStatus:
        """Perform actual connectivity check."""
        status = IntegrationStatus(name=info["display_name"], connected=False)
        status.last_check = datetime.now()
        
        try:
            # Read config from DB settings
            config_enabled = self._get_setting(f"{info['config_key_base']}.enabled", "1")
            if config_enabled != "1":
                status.connected = False
                status.last_error = "Integration disabled in settings"
                return status
            
            # Check based on integration type
            if name == "graphhopper":
                status = self._check_graphhopper(status)
            elif name == "nominatim":
                status = self._check_nominatim(status)
            elif name == "currency_api":
                status = self._check_currency_api(status)
            elif name == "fuel_price":
                status = self._check_fuel_price(status)
            elif name == "timocom":
                status = self._check_timocom(status)
            
        except Exception as e:
            status.connected = False
            status.last_error = str(e)[:200]
            logger.warning("Integration health check failed for %s: %s", name, e)
        
        if status.connected:
            status.last_success = datetime.now()
        
        return status
    
    def _get_setting(self, key: str, default: str = "") -> str:
        """Read a setting from the DB."""
        try:
            from repositories.settings_repository import SettingsRepository
            repo = SettingsRepository(self.db)
            value = repo.get(key)
            return value if value else default
        except Exception:
            return default
    
    def _check_graphhopper(self, status: IntegrationStatus) -> IntegrationStatus:
        """Check GraphHopper connectivity."""
        try:
            import os
            import requests
            url = os.environ.get("OPERION_GRAPHHOPPER_URL", "https://maps.operionerp.xyz")
            api_key = os.environ.get("OPERION_GRAPHHOPPER_API_KEY", "")
            if not api_key:
                status.last_error = "GraphHopper API key not configured"
                return status
            
            start = time.time()
            resp = requests.get(f"{url}/health", params={"key": api_key}, timeout=10)
            status.latency_ms = (time.time() - start) * 1000
            status.connected = resp.status_code == 200
            if not status.connected:
                status.last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            status.last_error = str(e)[:200]
        return status
    
    def _check_nominatim(self, status: IntegrationStatus) -> IntegrationStatus:
        """Check Nominatim connectivity."""
        try:
            import requests
            start = time.time()
            resp = requests.get("https://nominatim.openstreetmap.org/status", 
                               headers={"User-Agent": "OperionERP/1.0"}, timeout=10)
            status.latency_ms = (time.time() - start) * 1000
            status.connected = resp.status_code == 200
        except Exception as e:
            status.last_error = str(e)[:200]
        return status
    
    def _check_currency_api(self, status: IntegrationStatus) -> IntegrationStatus:
        """Check currency API health via existing service."""
        try:
            from services.currency_service import CurrencyService
            svc = CurrencyService()
            if svc.is_available():
                status.connected = True
            else:
                status.last_error = "Currency service reports unavailable"
        except Exception as e:
            status.last_error = str(e)[:200]
        return status
    
    def _check_fuel_price(self, status: IntegrationStatus) -> IntegrationStatus:
        """Check fuel price scraper health."""
        try:
            from services.fuel_price_service import FuelPriceService
            svc = FuelPriceService()
            if svc.is_available():
                status.connected = True
            else:
                status.last_error = "Fuel price service reports unavailable"
        except Exception as e:
            status.last_error = str(e)[:200]
        return status
    
    def _check_timocom(self, status: IntegrationStatus) -> IntegrationStatus:
        """Check TIMOCOM connectivity (placeholder)."""
        try:
            import os
            from services.http_client import ExternalHttpClient, HttpClientConfig
            url = os.environ.get("TIMOCOM_API_URL", "")
            api_key = os.environ.get("TIMOCOM_API_KEY", "")
            if not url or not api_key:
                status.last_error = "TIMOCOM not configured (API URL or key missing)"
                status.connected = False
                return status
            
            config = HttpClientConfig(
                base_url=url,
                timeout=10,
                max_retries=1,
                default_headers={"X-API-Key": api_key}
            )
            client = ExternalHttpClient(config)
            resp = client.get("/api/health")
            status.connected = resp.status_code == 200
            if not status.connected:
                status.last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            status.last_error = str(e)[:200]
        return status


def _status_to_dict(status: IntegrationStatus) -> Dict[str, Any]:
    return {
        "name": status.name,
        "connected": status.connected,
        "last_check": status.last_check.isoformat() if status.last_check else None,
        "last_success": status.last_success.isoformat() if status.last_success else None,
        "last_error": status.last_error,
        "latency_ms": round(status.latency_ms, 1) if status.latency_ms else None,
        "details": status.details,
    }
