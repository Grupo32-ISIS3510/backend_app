import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.telemetry.models import ScanEvent, ExpiryAccuracyEvent, ScreenEvent
from app.telemetry.schemas import (
    FailureBreakdownItem,
    ScanEventBatch,
    ScanEventCreate,
    ScanEventResponse,
    ScanStatsResponse,
    ExpiryAccuracyCreate,
    ExpiryAccuracyBatch,
    CategoryAccuracyItem,
    ExpiryStatsResponse,
    ScreenEventCreate,
    ScreenEventBatch,
    ScreenAbandonmentItem,
    AbandonmentStatsResponse,
)


def record_single_event(
    db: Session, user_id: uuid.UUID, payload: ScanEventCreate
) -> ScanEventResponse:
    obj = ScanEvent(
        user_id=user_id,
        timestamp=payload.timestamp,
        success=payload.success,
        failure_reason=payload.failure_reason,
        products_detected=payload.products_detected,
        duration_ms=payload.duration_ms,
    )
    db.add(obj)
    db.commit()
    return ScanEventResponse(received=1)


def record_batch(
    db: Session, user_id: uuid.UUID, batch: ScanEventBatch
) -> ScanEventResponse:
    objects = [
        ScanEvent(
            user_id=user_id,
            timestamp=evt.timestamp,
            success=evt.success,
            failure_reason=evt.failure_reason,
            products_detected=evt.products_detected,
            duration_ms=evt.duration_ms,
        )
        for evt in batch.events
    ]
    db.bulk_save_objects(objects)
    db.commit()
    return ScanEventResponse(received=len(objects))


def get_scan_stats(
    db: Session, user_id: uuid.UUID, days: int
) -> ScanStatsResponse:
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(ScanEvent).filter(
        ScanEvent.user_id == user_id,
        ScanEvent.timestamp >= since,
    )

    total = base.count()
    if total == 0:
        return ScanStatsResponse(
            total_scans=0,
            successful_scans=0,
            failed_scans=0,
            crash_rate=0.0,
            avg_duration_ms=0.0,
            failure_breakdown=[],
        )

    successful = base.filter(ScanEvent.success.is_(True)).count()
    failed = total - successful

    avg_ms = (
        db.query(func.avg(ScanEvent.duration_ms))
        .filter(
            ScanEvent.user_id == user_id,
            ScanEvent.timestamp >= since,
        )
        .scalar() or 0
    )

    breakdown_rows = (
        db.query(
            ScanEvent.failure_reason,
            func.count(ScanEvent.id).label("cnt"),
        )
        .filter(
            ScanEvent.user_id == user_id,
            ScanEvent.timestamp >= since,
            ScanEvent.success.is_(False),
        )
        .group_by(ScanEvent.failure_reason)
        .order_by(func.count(ScanEvent.id).desc())
        .all()
    )

    return ScanStatsResponse(
        total_scans=total,
        successful_scans=successful,
        failed_scans=failed,
        crash_rate=round(failed / total, 4),
        avg_duration_ms=round(float(avg_ms), 1),
        failure_breakdown=[
            FailureBreakdownItem(
                reason=row.failure_reason or "unknown",
                count=row.cnt,
            )
            for row in breakdown_rows
        ],
    )


def get_global_scan_stats(db: Session, days: int) -> ScanStatsResponse:
    """Stats de todos los usuarios (para dashboard admin)."""
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(ScanEvent).filter(ScanEvent.timestamp >= since)

    total = base.count()
    if total == 0:
        return ScanStatsResponse(
            total_scans=0,
            successful_scans=0,
            failed_scans=0,
            crash_rate=0.0,
            avg_duration_ms=0.0,
            failure_breakdown=[],
        )

    successful = base.filter(ScanEvent.success.is_(True)).count()
    failed = total - successful

    avg_ms = (
        db.query(func.avg(ScanEvent.duration_ms))
        .filter(ScanEvent.timestamp >= since)
        .scalar() or 0
    )

    breakdown_rows = (
        db.query(
            ScanEvent.failure_reason,
            func.count(ScanEvent.id).label("cnt"),
        )
        .filter(ScanEvent.timestamp >= since, ScanEvent.success.is_(False))
        .group_by(ScanEvent.failure_reason)
        .order_by(func.count(ScanEvent.id).desc())
        .all()
    )

    return ScanStatsResponse(
        total_scans=total,
        successful_scans=successful,
        failed_scans=failed,
        crash_rate=round(failed / total, 4),
        avg_duration_ms=round(float(avg_ms), 1),
        failure_breakdown=[
            FailureBreakdownItem(
                reason=row.failure_reason or "unknown",
                count=row.cnt,
            )
            for row in breakdown_rows
        ],
    )


# ── T3.3  Expiry Accuracy ────────────────────────────────────

def record_expiry_accuracy(
    db: Session, user_id: uuid.UUID, payload: ExpiryAccuracyCreate
) -> ScanEventResponse:
    obj = ExpiryAccuracyEvent(
        user_id=user_id,
        timestamp=payload.timestamp,
        category=payload.category,
        ocr_detected_date=payload.ocr_detected_date,
        ocr_date=payload.ocr_date,
        user_confirmed_date=payload.user_confirmed_date,
        accurate=payload.accurate,
    )
    db.add(obj)
    db.commit()
    return ScanEventResponse(received=1)


def record_expiry_accuracy_batch(
    db: Session, user_id: uuid.UUID, batch: ExpiryAccuracyBatch
) -> ScanEventResponse:
    objects = [
        ExpiryAccuracyEvent(
            user_id=user_id,
            timestamp=evt.timestamp,
            category=evt.category,
            ocr_detected_date=evt.ocr_detected_date,
            ocr_date=evt.ocr_date,
            user_confirmed_date=evt.user_confirmed_date,
            accurate=evt.accurate,
        )
        for evt in batch.events
    ]
    db.bulk_save_objects(objects)
    db.commit()
    return ScanEventResponse(received=len(objects))


def get_expiry_stats(
    db: Session, days: int
) -> ExpiryStatsResponse:
    since = datetime.utcnow() - timedelta(days=days)
    base = db.query(ExpiryAccuracyEvent).filter(
        ExpiryAccuracyEvent.timestamp >= since
    )
    total = base.count()
    if total == 0:
        return ExpiryStatsResponse(
            total_events=0,
            overall_detection_rate=0.0,
            overall_accuracy_rate=0.0,
            by_category=[],
        )

    detected = base.filter(ExpiryAccuracyEvent.ocr_detected_date.is_(True)).count()
    accurate = base.filter(ExpiryAccuracyEvent.accurate.is_(True)).count()

    rows = (
        db.query(
            ExpiryAccuracyEvent.category,
            func.count(ExpiryAccuracyEvent.id).label("total"),
            func.count(ExpiryAccuracyEvent.id).filter(
                ExpiryAccuracyEvent.ocr_detected_date.is_(True)
            ).label("ocr_detected"),
            func.count(ExpiryAccuracyEvent.id).filter(
                ExpiryAccuracyEvent.accurate.is_(True)
            ).label("accurate"),
        )
        .filter(ExpiryAccuracyEvent.timestamp >= since)
        .group_by(ExpiryAccuracyEvent.category)
        .order_by(ExpiryAccuracyEvent.category)
        .all()
    )

    return ExpiryStatsResponse(
        total_events=total,
        overall_detection_rate=round(detected / total, 4) if total else 0.0,
        overall_accuracy_rate=round(accurate / detected, 4) if detected else 0.0,
        by_category=[
            CategoryAccuracyItem(
                category=row.category,
                total=row.total,
                ocr_detected=row.ocr_detected,
                accurate=row.accurate,
                accuracy_rate=round(row.accurate / row.ocr_detected, 4) if row.ocr_detected else 0.0,
            )
            for row in rows
        ],
    )


# ── T3.5  Screen Events / Abandonment ────────────────────────

def record_screen_event(
    db: Session, user_id: uuid.UUID, payload: ScreenEventCreate
) -> ScanEventResponse:
    obj = ScreenEvent(
        user_id=user_id,
        timestamp=payload.timestamp,
        screen_name=payload.screen_name,
        event_type=payload.event_type,
        exit_reason=payload.exit_reason,
        dwell_time_ms=payload.dwell_time_ms,
    )
    db.add(obj)
    db.commit()
    return ScanEventResponse(received=1)


def record_screen_event_batch(
    db: Session, user_id: uuid.UUID, batch: ScreenEventBatch
) -> ScanEventResponse:
    objects = [
        ScreenEvent(
            user_id=user_id,
            timestamp=evt.timestamp,
            screen_name=evt.screen_name,
            event_type=evt.event_type,
            exit_reason=evt.exit_reason,
            dwell_time_ms=evt.dwell_time_ms,
        )
        for evt in batch.events
    ]
    db.bulk_save_objects(objects)
    db.commit()
    return ScanEventResponse(received=len(objects))


def get_abandonment_stats(
    db: Session, days: int
) -> AbandonmentStatsResponse:
    since = datetime.utcnow() - timedelta(days=days)

    enters = (
        db.query(
            ScreenEvent.screen_name,
            func.count(ScreenEvent.id).label("cnt"),
        )
        .filter(
            ScreenEvent.timestamp >= since,
            ScreenEvent.event_type == "enter",
        )
        .group_by(ScreenEvent.screen_name)
        .all()
    )

    completed = (
        db.query(
            ScreenEvent.screen_name,
            func.count(ScreenEvent.id).label("cnt"),
        )
        .filter(
            ScreenEvent.timestamp >= since,
            ScreenEvent.event_type == "exit",
            ScreenEvent.exit_reason.in_(["completed", "completed_manual", "scan_started"]),
        )
        .group_by(ScreenEvent.screen_name)
        .all()
    )

    completed_map = {row.screen_name: row.cnt for row in completed}
    total_sessions = sum(row.cnt for row in enters)

    screens = []
    for row in enters:
        comp = completed_map.get(row.screen_name, 0)
        aband = row.cnt - comp
        screens.append(
            ScreenAbandonmentItem(
                screen_name=row.screen_name,
                total_enters=row.cnt,
                completed=comp,
                abandoned=max(aband, 0),
                abandonment_rate=round(max(aband, 0) / row.cnt, 4) if row.cnt else 0.0,
            )
        )

    return AbandonmentStatsResponse(
        total_sessions=total_sessions,
        screens=screens,
    )
