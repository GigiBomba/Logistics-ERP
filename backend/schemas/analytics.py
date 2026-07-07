from typing import Any, Dict

from pydantic import BaseModel, ConfigDict

class AnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: Dict[str, Any]
    cached: bool = False
