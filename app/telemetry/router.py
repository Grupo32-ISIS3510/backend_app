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
    ExpiryAccuracyCreate,
    ExpiryAccuracyBatch,
    ExpiryStatsResponse,
    ScreenEventCreate,
    ScreenEventBatch,
    AbandonmentStatsResponse,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


# ── Scan Events (Sprint 2) ───────────────────────────────────

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


# ── T3.3  Expiry Accuracy ────────────────────────────────────

@router.post("/expiry-accuracy", response_model=ScanEventResponse, status_code=201)
def record_expiry_accuracy(
    payload: ExpiryAccuracyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra un evento de precisión de fecha de vencimiento OCR."""
    return telemetry_service.record_expiry_accuracy(db, current_user.id, payload)


@router.post("/expiry-accuracy/batch", response_model=ScanEventResponse, status_code=201)
def record_expiry_accuracy_batch(
    batch: ExpiryAccuracyBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra múltiples eventos de precisión de fecha acumulados offline."""
    return telemetry_service.record_expiry_accuracy_batch(db, current_user.id, batch)


@router.get("/expiry-stats", response_model=ExpiryStatsResponse)
def get_expiry_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de precisión OCR de fechas de vencimiento por categoría."""
    return telemetry_service.get_expiry_stats(db, days)


# ── T3.5  Screen Events / Abandonment ────────────────────────

@router.post("/screen-events", response_model=ScanEventResponse, status_code=201)
def record_screen_event(
    payload: ScreenEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra un evento de navegación de pantalla."""
    return telemetry_service.record_screen_event(db, current_user.id, payload)


@router.post("/screen-events/batch", response_model=ScanEventResponse, status_code=201)
def record_screen_event_batch(
    batch: ScreenEventBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra múltiples eventos de pantalla acumulados offline."""
    return telemetry_service.record_screen_event_batch(db, current_user.id, batch)


@router.get("/abandonment-stats", response_model=AbandonmentStatsResponse)
def get_abandonment_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estadísticas de tasa de abandono por pantalla de registro de alimentos."""
    return telemetry_service.get_abandonment_stats(db, days)
