from pydantic import BaseModel
from typing import Optional


class DeviceTokenRegister(BaseModel):
    fcm_token: str
    platform: str   # 'android_kotlin', 'android_flutter', 'ios_flutter'


class NotificationPreferenceUpdate(BaseModel):
    days_before_expiry: Optional[int] = None
    quiet_hours_start:  Optional[int] = None   # 0-23
    quiet_hours_end:    Optional[int] = None   # 0-23
    push_enabled:       Optional[bool] = None


class NotificationPreferenceResponse(BaseModel):
    days_before_expiry: int
    quiet_hours_start:  Optional[int]
    quiet_hours_end:    Optional[int]
    push_enabled:       bool

    class Config:
        from_attributes = True


class TestSendSelfRequest(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    route: str = "/home"
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    days_remaining: Optional[int] = None


class NotificationDispatchReport(BaseModel):
    status: str
    sent_count: int
    failed_count: int
    invalid_tokens_count: int
    reason: Optional[str] = None
