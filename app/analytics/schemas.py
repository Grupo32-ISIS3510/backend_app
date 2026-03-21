from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, UUID4


# ── Analytics Events (Event Ingestion) ───────────────────────────────────────

class AnalyticsEventCreate(BaseModel):
    """Schema para recibir un evento de analytics desde el frontend."""
    event_name: str
    user_id: UUID4
    timestamp: int  # Unix timestamp en milisegundos
    properties: Optional[Dict[str, Any]] = None


class AnalyticsEventBatchRequest(BaseModel):
    """Schema para recibir un batch de eventos de analytics."""
    events: List[AnalyticsEventCreate]


class AnalyticsEventResponse(BaseModel):
    """Schema de respuesta para un evento de analytics almacenado."""
    id: UUID4
    event_name: str
    timestamp: int
    properties: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyticsEventBatchResponse(BaseModel):
    """Respuesta para el endpoint de batch de eventos."""
    status: str
    events_received: int
    message: str


# ── Analytics Dashboard (Read-Only) ──────────────────────────────────────────


class SavingsResponse(BaseModel):
    saved_cop: Decimal      # dinero "rescatado": consumido con ≤ 3 días antes de vencer
    wasted_cop: Decimal     # dinero perdido: total de ítems descartados
    period: str             # formato "YYYY-MM"


class WasteTrendItem(BaseModel):
    month: str              # formato "YYYY-MM"
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
    segment: str            # 'proactive' | 'neutral' | 'passive'
    recipes_cooked_last_30_days: int
    open_rate: float


class DashboardResponse(BaseModel):
    savings: SavingsResponse
    waste_summary: WasteSummaryResponse
    segment: UserSegmentResponse
