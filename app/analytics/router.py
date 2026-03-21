from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.analytics import service as analytics_service
from app.analytics.schemas import (
    AnalyticsEventBatchRequest,
    AnalyticsEventBatchResponse,
    DashboardResponse,
    SavingsResponse,
    UserSegmentResponse,
    WasteSummaryResponse,
    WasteTrendItem,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

_now = datetime.utcnow()


@router.post("/events", response_model=AnalyticsEventBatchResponse, status_code=status.HTTP_201_CREATED)
def store_events(
    data: AnalyticsEventBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Almacena un batch de eventos de analytics enviados desde el frontend.
    Los eventos se usan para análisis de comportamiento y mejoras de la app.
    """
    stored_count = analytics_service.store_analytics_events(db, current_user.id, data.events)
    
    return AnalyticsEventBatchResponse(
        status="success",
        events_received=stored_count,
        message=f"{stored_count} eventos almacenados exitosamente."
    )


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
