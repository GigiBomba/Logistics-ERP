"""Request schemas for the AutoMail API router."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AutomailTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=255)
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    variables_json: Optional[str] = None
    is_default: Optional[int] = 0


class AutomailTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    subject: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    variables_json: Optional[str] = None
    is_default: Optional[int] = None


class AutomailScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=255)
    trigger_type: str = "days_before_due"
    days_offset: int = 3
    template_id: int = 0
    is_active: Optional[int] = 1
    sort_order: Optional[int] = None
    attach_invoice: Optional[int] = 1
    attach_cmr: Optional[int] = 1
    attach_all_docs: Optional[int] = 0


class AutomailScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    trigger_type: Optional[str] = None
    days_offset: Optional[int] = None
    template_id: Optional[int] = None
    is_active: Optional[int] = None
    sort_order: Optional[int] = None
    attach_invoice: Optional[int] = None
    attach_cmr: Optional[int] = None
    attach_all_docs: Optional[int] = None


class AutomailSchedulesReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: List[int] = Field(default_factory=list)


class AutomailSettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(default="", max_length=2000)


class AutomailTripRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: Optional[int] = None


class AutomailManualSend(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_id: Optional[int] = None
    recipient: str = ""


class AutomailSendNow(AutomailManualSend):
    pass


class AutomailSendTest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: str
    subject: str = ""
    body: str = ""
    html: bool = False
