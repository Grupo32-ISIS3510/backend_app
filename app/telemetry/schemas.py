from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Scan Events ──────────────────────────────────────────────

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


# ── Expiry Accuracy (T3.3) ───────────────────────────────────

class ExpiryAccuracyCreate(BaseModel):
    timestamp: datetime
    category: str = Field(..., max_length=100)
    ocr_detected_date: bool
    ocr_date: Optional[date] = None
    user_confirmed_date: date
    accurate: bool


class ExpiryAccuracyBatch(BaseModel):
    events: list[ExpiryAccuracyCreate] = Field(..., min_length=1, max_length=200)


class CategoryAccuracyItem(BaseModel):
    category: str
    total: int
    ocr_detected: int
    accurate: int
    accuracy_rate: float


class ExpiryStatsResponse(BaseModel):
    total_events: int
    overall_detection_rate: float
    overall_accuracy_rate: float
    by_category: list[CategoryAccuracyItem]


# ── Screen Events / Abandonment (T3.5) ───────────────────────

class ScreenEventCreate(BaseModel):
    timestamp: datetime
    screen_name: str = Field(..., max_length=100)
    event_type: str = Field(..., pattern=r"^(enter|exit)$")
    exit_reason: Optional[str] = Field(None, max_length=100)
    dwell_time_ms: int = Field(0, ge=0)


class ScreenEventBatch(BaseModel):
    events: list[ScreenEventCreate] = Field(..., min_length=1, max_length=500)


class ScreenAbandonmentItem(BaseModel):
    screen_name: str
    total_enters: int
    completed: int
    abandoned: int
    abandonment_rate: float


class AbandonmentStatsResponse(BaseModel):
    total_sessions: int
    screens: list[ScreenAbandonmentItem]


# ── Feature Usage (T3.1) ─────────────────────────────────────

class FeatureUsageCreate(BaseModel):
    timestamp: datetime
    feature: str = Field(..., max_length=50)


class FeatureUsageBatch(BaseModel):
    events: list[FeatureUsageCreate] = Field(..., min_length=1, max_length=500)


class FeatureFrequencyBucket(BaseModel):
    """Distribución: cuántos usuarios usaron la feature N veces en la ventana."""
    bucket: str   # ej: "1", "2-5", "6-10", "11+"
    users: int


class FeatureUsageItem(BaseModel):
    feature: str
    total_uses: int
    active_users: int           # usuarios distintos que la usaron en la ventana
    avg_uses_per_user: float    # total_uses / active_users
    distribution: list[FeatureFrequencyBucket]


class FeatureUsageStatsResponse(BaseModel):
    period_days: int
    active_users: int           # usuarios distintos que usaron CUALQUIER feature
    features: list[FeatureUsageItem]
