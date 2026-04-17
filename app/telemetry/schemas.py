from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ScanEventCreate(BaseModel):
    timestamp: datetime
    success: bool
    failure_reason: Optional[str] = Field(None, max_length=255)
    products_detected: int = Field(0, ge=0)
    duration_ms: int = Field(0, ge=0)


class ScanEventBatch(BaseModel):
    events: list[ScanEventCreate] = Field(..., min_length=1, max_length=200)


class ScanEventResponse(BaseModel):
    received: int


class FailureBreakdownItem(BaseModel):
    reason: str
    count: int


class ScanStatsResponse(BaseModel):
    total_scans: int
    successful_scans: int
    failed_scans: int
    crash_rate: float
    avg_duration_ms: float
    failure_breakdown: list[FailureBreakdownItem]
