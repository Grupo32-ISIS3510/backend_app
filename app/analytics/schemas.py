from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


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
