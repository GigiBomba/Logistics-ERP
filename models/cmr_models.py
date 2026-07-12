from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
from .common import ServiceResult


class CmrGenerateRequest(BaseModel):
    trip_id: int
    language: str = "ro"  # ro, en, de, fr
    copies: int = 3
    include_stamps: bool = True
    sender_name: str = ""
    sender_address: str = ""
    carrier_name: str = ""
    carrier_license: str = ""
    remarks: str = ""


class CmrResult(BaseModel):
    cmr_number: str
    trip_id: int
    file_path: str
    copies: int
    generated_at: datetime
    cmr_data: dict = {}  # all fields that went into the CMR


CmrGenerateResult = ServiceResult[CmrResult]
