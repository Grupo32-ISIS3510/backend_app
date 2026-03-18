from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.analytics import service as analytics_service
from app.analytics.schemas import (
    AnalyticsEventBatch,
    AnalyticsEventResponse,
    DashboardResponse,
    EventsSummaryResponse,
    SavingsResponse,
    UserSegmentResponse,
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
