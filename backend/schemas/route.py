from pydantic import BaseModel, ConfigDict

class RouteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str = ""
    total_km: float = 0.0


class RouteResponse(RouteBase):
    id: int
    profile: str = ""
    created_at: str = ""
