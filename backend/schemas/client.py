
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ClientBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    email: str = ""
    phone: str = ""
    address: Optional[str] = None


class ClientResponse(ClientBase):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_active: bool = True
    created_at: str = ""
