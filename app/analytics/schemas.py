from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, UUID4

from pydantic import BaseModel, Field


# ── Capture / Transport schemas ──────────────────────────────────────────────

class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(..., max_length=100)
    properties: Optional[dict] = None
    session_id: Optional[str] = Field(None, max_length=100)
    platform: Optional[str] = Field(None, max_length=20)
    app_version: Optional[str] = Field(None, max_length=20)
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


# ── T4.2: Market / demand insights (cross-user, anonymized) ──────────────────

class ProductTrendItem(BaseModel):
    product_name: str
    category: Optional[str]
    consumption_count: int
    unique_users: int
    repurchase_rate: float
    avg_consumption_per_user: float


class CategoryTrendItem(BaseModel):
    category: str
    total_consumption: int
    unique_users: int
    top_product: Optional[str]


class MarketProductTrendsResponse(BaseModel):
    generated_at: datetime
    total_users_analyzed: int
    top_n: int
    products: list[ProductTrendItem]
    categories: list[CategoryTrendItem]


class SeedDemoResponse(BaseModel):
    status: str
    users_created: int
    items_created: int
    events_created: int


# ── T1.1: Notification latency & inventory events ────────────────────────────

class LatencyBucket(BaseModel):
    bucket: str
    count: int


class NotificationLatencyResponse(BaseModel):
    avg_seconds: float
    p50_seconds: float
    p95_seconds: float
    max_seconds: float
    sample_size: int
    histogram: list[LatencyBucket]
    period_days: int


class InventoryEventsSummaryResponse(BaseModel):
    total_registered: int
    eligible_for_alert: int
    period_days: int


# ── T2.3: Recipe interactions ─────────────────────────────────────────────────

class RecipeInteractionsSummary(BaseModel):
    total_cooked: int
    total_viewed: int
    cook_through_rate: float
    avg_inventory_matches_on_cook: Optional[float]
    period_days: int


class TopCookedRecipe(BaseModel):
    name: str
    cooks: int


class ViewsVsCooksRow(BaseModel):
    name: str
    views: int
    cooks: int
    rate_pct: Optional[float]


class MatchBucket(BaseModel):
    matches: str
    count: int


# ── T3.4: Alert response times ────────────────────────────────────────────────

class AlertResponseBucket(BaseModel):
    bucket: str
    count: int


class AlertResponseCategoryStat(BaseModel):
    category: str
    sample_size: int
    avg_minutes: float
    p50_minutes: float


class AlertResponseTimesResponse(BaseModel):
    avg_minutes: float
    p50_minutes: float
    p95_minutes: float
    max_minutes: float
    sample_size: int
    period_days: int
    histogram: list[AlertResponseBucket]
    by_category: list[AlertResponseCategoryStat]


# ── T3.2: Waste reduction by recipe category ────────────────────────────────

class WasteReductionByRecipeCategoryItem(BaseModel):
    recipe_category: Optional[str]
    cooks: int                 # # de interacciones 'cooked' en la ventana
    items_rescued: int         # ítems consumidos vía esa categoría dentro del umbral pre-vencimiento
    items_consumed_total: int  # total de ítems consumidos vía esa categoría
    value_rescued_cop: Decimal
    rescue_rate: float         # items_rescued / items_consumed_total  (0..1)
    unique_users: int


class WasteReductionByRecipeCategoryResponse(BaseModel):
    period_days: int
    rescue_window_days: int    # un ítem cuenta como "rescatado" si fue consumido a ≤ N días de su expiry
    total_cooks: int
    total_items_rescued: int
    total_value_rescued_cop: Decimal
    by_category: list[WasteReductionByRecipeCategoryItem]


# ── T3.6: Favorites distribution ─────────────────────────────────────────────

class FavoriteCategoryItem(BaseModel):
    category: Optional[str]
    favorites_count: int
    unique_users: int
    pct_of_total: float        # 0..1


class FavoriteIngredientItem(BaseModel):
    ingredient_name: str
    favorites_count: int       # # de favoritos que tienen este ingrediente
    pct_of_total: float


class FavoritesDistributionResponse(BaseModel):
    total_favorites: int
    unique_users: int
    by_category: list[FavoriteCategoryItem]
    top_ingredients: list[FavoriteIngredientItem]


# ── T4.1: Segments behavioral patterns ───────────────────────────────────────

class SegmentPatternItem(BaseModel):
    segment: str                     # 'passive' | 'neutral' | 'proactive'
    user_count: int
    avg_recipes_cooked_30d: float
    avg_notification_open_rate: float
    avg_items_registered_30d: float
    avg_items_wasted_30d: float
    avg_alert_response_hours: Optional[float]
    avg_favorites: float
    top_features: list[str]          # features más usadas dentro del segmento


class SegmentsPatternsResponse(BaseModel):
    period_days: int
    total_users_analyzed: int
    segments: list[SegmentPatternItem]
