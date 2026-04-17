from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.telemetry import service as telemetry_service
from app.telemetry.schemas import (
    ScanEventBatch,
    ScanEventCreate,
    ScanEventResponse,
    ScanStatsResponse,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


@router.post("/scan-events", response_model=ScanEventResponse, status_code=201)
def record_scan_event(
    payload: ScanEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra un evento de escaneo OCR individual desde el móvil."""
    return telemetry_service.record_single_event(db, current_user.id, payload)


@router.post("/scan-events/batch", response_model=ScanEventResponse, status_code=201)
def record_scan_events_batch(
    batch: ScanEventBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra múltiples eventos de escaneo acumulados offline."""
    return telemetry_service.record_batch(db, current_user.id, batch)


@router.get("/scan-stats", response_model=ScanStatsResponse)
def get_scan_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de escaneo OCR del usuario autenticado."""
    return telemetry_service.get_scan_stats(db, current_user.id, days)


@router.get("/scan-stats/global", response_model=ScanStatsResponse)
def get_global_scan_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de escaneo OCR de TODOS los usuarios (para dashboard admin)."""
    return telemetry_service.get_global_scan_stats(db, days)
