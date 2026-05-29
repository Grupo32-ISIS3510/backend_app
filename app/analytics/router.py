from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.analytics import service as analytics_service
from app.analytics.schemas import (
    AlertResponseTimesResponse,
    AnalyticsEventBatch,
    AnalyticsEventResponse,
    DashboardResponse,
    EventsSummaryResponse,
    FavoritesDistributionResponse,
    MarketProductTrendsResponse,
    SavingsResponse,
    SeedDemoResponse,
    InventoryEventsSummaryResponse,
    MarketProductTrendsResponse,
    MatchBucket,
    NotificationLatencyResponse,
    RecipeInteractionsSummary,
    SavingsResponse,
    SeedDemoResponse,
    SegmentsPatternsResponse,
    TopCookedRecipe,
    UserSegmentResponse,
    ViewsVsCooksRow,
    WasteReductionByRecipeCategoryResponse,
    WasteSummaryResponse,
    WasteTrendItem,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

_now = datetime.utcnow()


# ── Pipeline: Capture ────────────────────────────────────────────────────────

@router.post("/events", response_model=AnalyticsEventResponse, status_code=201)
def ingest_events(
    batch: AnalyticsEventBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recibe un batch de eventos analytics desde el cliente móvil (max 100 por request)."""
    return analytics_service.record_events(db, current_user.id, batch)


@router.get("/events/summary", response_model=EventsSummaryResponse)
def get_events_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen de eventos analytics agrupados por tipo en los últimos N días."""
    return analytics_service.get_events_summary(db, current_user.id, days)


# ── Pipeline: Consume ────────────────────────────────────────────────────────

@router.get("/savings", response_model=SavingsResponse)
def get_savings(
    month: int = Query(_now.month, ge=1, le=12),
    year: int = Query(_now.year, ge=2020),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dinero rescatado vs perdido en un mes dado."""
    return analytics_service.get_monthly_savings(db, current_user.id, month, year)


@router.get("/waste", response_model=list[WasteTrendItem])
def get_waste_trends(
    months: int = Query(3, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tendencia de desperdicios por mes y categoría en los últimos N meses."""
    return analytics_service.get_waste_trends(db, current_user.id, months)


@router.get("/summary", response_model=WasteSummaryResponse)
def get_waste_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen histórico: consumido vs descartado, racha sin desperdiciar."""
    return analytics_service.get_waste_summary(db, current_user.id)


@router.get("/segment", response_model=UserSegmentResponse)
def get_user_segment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Segmento del usuario: 'proactive', 'neutral' o 'passive'."""
    return analytics_service.get_user_segment(db, current_user.id)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    month: int = Query(_now.month, ge=1, le=12),
    year: int = Query(_now.year, ge=2020),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Todas las métricas en un solo request — optimizado para la pantalla de inicio."""
    return analytics_service.get_dashboard(db, current_user.id, month, year)


# ── T4.2: Market / demand insights ───────────────────────────────────────────

@router.post("/market/seed-demo", response_model=SeedDemoResponse, status_code=201)
def seed_demo_market_data(db: Session = Depends(get_db)):
    """
    Pobla la base de datos con 6 usuarios sintéticos y sus patrones de compra/consumo.
    Idempotente: si los usuarios demo ya existen, devuelve `already_seeded`.
    No requiere autenticación (solo para entornos de demo/desarrollo).
    """
    return analytics_service.seed_demo_market_data(db)


@router.get("/market/top-products", response_model=MarketProductTrendsResponse)
def get_top_products(
    top_n: int = Query(10, ge=1, le=50, description="Número de productos a retornar"),
    category: str = Query(None, description="Filtrar por categoría (ej. 'Lácteos')"),
    min_users: int = Query(1, ge=1, description="Mínimo de usuarios distintos que consumieron el producto"),
    db: Session = Depends(get_db),
):
    """
    T4.2 – Productos y categorías con mayor frecuencia de consumo y tasa de recompra.

    Responde la pregunta de negocio: *¿qué productos o categorías muestran mayor frecuencia
    de consumo y tasa de recompra entre usuarios?*

    - **consumption_count**: total de veces consumido en toda la base de usuarios.
    - **unique_users**: usuarios distintos que lo consumieron.
    - **repurchase_rate**: fracción de esos usuarios que registraron el mismo producto ≥ 2 veces.
    - **avg_consumption_per_user**: promedio de eventos de consumo por usuario.

    Los datos son agregados y anónimos — no se expone ningún identificador de usuario.
    Ejecutar primero `POST /market/seed-demo` si la BD está vacía.
    """
    return analytics_service.get_top_products(db, top_n=top_n, category=category, min_users=min_users)


# ── T1.1: Notification latency & inventory events ────────────────────────────

@router.get("/notification-latency", response_model=NotificationLatencyResponse)
def notification_latency(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Latencia entre registro de ítem y primera notificación recibida."""
    return analytics_service.get_notification_latency(db, days=days)


@router.get("/inventory-events/summary", response_model=InventoryEventsSummaryResponse)
def inventory_events_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Total de ítems registrados y cuántos eran elegibles para alerta (≤3 días al vencer)."""
    return analytics_service.get_inventory_events_summary(db, days=days)


# ── T2.3: Recipe interactions ─────────────────────────────────────────────────

@router.get("/recipe-interactions/summary", response_model=RecipeInteractionsSummary)
def recipe_interactions_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resumen de interacciones: total cocinado/visto, cook-through rate y matches promedio."""
    return analytics_service.get_recipe_interactions_summary(db, days=days)


@router.get("/recipe-interactions/top-cooked", response_model=list[TopCookedRecipe])
def top_cooked_recipes(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ranking de recetas más cocinadas en los últimos N días."""
    return analytics_service.get_top_cooked_recipes(db, days=days, limit=limit)


@router.get("/recipe-interactions/views-vs-cooks", response_model=list[ViewsVsCooksRow])
def views_vs_cooks(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Comparativo de vistas vs cocinadas por receta con cook-through rate individual."""
    return analytics_service.get_views_vs_cooks(db, days=days, limit=limit)


@router.get("/recipe-interactions/match-distribution", response_model=list[MatchBucket])
def match_distribution(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Histograma de inventory_matches al momento de cocinar (1/2/3/4/5+)."""
    return analytics_service.get_match_distribution(db, days=days)


# ── T3.4: Alert response times (Dashboard BQ T3.4) ───────────────────────────

@router.get("/alert-response-times", response_model=AlertResponseTimesResponse)
def alert_response_times(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """BQ T3.4 — Distribución del tiempo de respuesta a alertas de vencimiento.

    Mide los minutos entre el envío de la alerta (notification_dispatches,
    status='sent') y la primera acción del usuario sobre el ítem (consumed/
    discarded). Solo incluye despachos que derivaron en acción posterior
    (= "usuarios que toman acción"). Devuelve avg/p50/p95/max en minutos,
    un histograma de 8 buckets (< 5 min ... > 24 h) y un desglose por
    categoría (más lentas primero, candidatas a alertar con más anticipación).
    Si la muestra global es < 5, devuelve ceros con arrays vacíos."""
    return analytics_service.get_alert_response_times(db, current_user.id, days)


# ── T3.2: Waste reduction by recipe category ────────────────────────────────

@router.get(
    "/waste-reduction-by-recipe-category",
    response_model=WasteReductionByRecipeCategoryResponse,
)
def waste_reduction_by_recipe_category(
    days: int = Query(30, ge=1, le=365),
    rescue_window_days: int = Query(3, ge=1, le=14),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """T3.2 — Distribución del impacto de las recomendaciones de recetas en la
    reducción de desperdicio, agrupada por categoría de receta.

    Cuenta como "rescatado" un ítem que fue consumido al cocinar una receta y
    estaba a ≤ `rescue_window_days` de su fecha de expiración. Cross-user.
    """
    return analytics_service.get_waste_reduction_by_recipe_category(
        db, days=days, rescue_window_days=rescue_window_days
    )


# ── T3.6: Favorites distribution ─────────────────────────────────────────────

@router.get("/favorites-distribution", response_model=FavoritesDistributionResponse)
def favorites_distribution(
    top_ingredients: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """T3.6 — Cómo se distribuyen las categorías de recetas e ingredientes
    principales de las recetas marcadas como favoritas (cross-user, agregado)."""
    return analytics_service.get_favorites_distribution(db, top_ingredients=top_ingredients)


# ── T4.1: Segments behavioral patterns ───────────────────────────────────────

@router.get("/segments/patterns", response_model=SegmentsPatternsResponse)
def segments_patterns(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """T4.1 — Patrones de comportamiento que distinguen usuarios Passive vs
    Proactive (vs Neutral). Por cada segmento devuelve: # de usuarios, promedio
    de recetas cocinadas, open rate de notificaciones, ítems registrados,
    ítems desperdiciados, tiempo de respuesta a alertas, favoritos y top
    features usadas."""
    return analytics_service.get_segments_patterns(db, days=days)
