
from pydantic import BaseModel

class ClientBase(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


class ClientResponse(ClientBase):
    id: int
    is_active: bool = True
    created_at: str = ""
