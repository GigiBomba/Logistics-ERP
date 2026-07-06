from typing import Any, Dict

from pydantic import BaseModel

class AnalyticsResponse(BaseModel):
    data: Dict[str, Any]
    cached: bool = False
