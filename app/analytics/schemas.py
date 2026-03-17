from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ── Capture / Transport schemas ──────────────────────────────────────────────

class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(..., max_length=100)
    properties: dict | None = None
    session_id: str | None = Field(None, max_length=100)
    platform: str | None = Field(None, max_length=20)
    app_version: str | None = Field(None, max_length=20)
    occurred_at: datetime


class AnalyticsEventBatch(BaseModel):
    events: list[AnalyticsEventCreate] = Field(..., min_length=1, max_length=100)


class AnalyticsEventResponse(BaseModel):
    received: int
    duplicates_skipped: int


# ── Events summary ───────────────────────────────────────────────────────────

class EventCount(BaseModel):
    event_name: str
    count: int


class EventsSummaryResponse(BaseModel):
    total_events: int
    period_days: int
    breakdown: list[EventCount]


# ── Existing aggregate schemas ───────────────────────────────────────────────

class SavingsResponse(BaseModel):
    saved_cop: Decimal
    wasted_cop: Decimal
    period: str


class WasteTrendItem(BaseModel):
    month: str
    category: Optional[str] = None
    items_discarded: int
    value_lost_cop: Decimal


class WasteSummaryResponse(BaseModel):
    total_consumed: int
    total_discarded: int
    most_wasted_category: Optional[str] = None
    most_discarded_item: Optional[str] = None
    no_waste_streak_days: int


class UserSegmentResponse(BaseModel):
    segment: str
    recipes_cooked_last_30_days: int
    open_rate: float


class DashboardResponse(BaseModel):
    savings: SavingsResponse
    waste_trends: list[WasteTrendItem]
    waste_summary: WasteSummaryResponse
    segment: UserSegmentResponse
