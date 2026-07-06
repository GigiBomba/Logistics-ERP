from pydantic import BaseModel

class RouteBase(BaseModel):
    fingerprint: str = ""
    total_km: float = 0.0


class RouteResponse(RouteBase):
    id: int
    profile: str = ""
    created_at: str = ""
