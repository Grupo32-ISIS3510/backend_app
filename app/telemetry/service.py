import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.telemetry.models import ScanEvent
from app.telemetry.schemas import (
    FailureBreakdownItem,
    ScanEventBatch,
    ScanEventCreate,
    ScanEventResponse,
    ScanStatsResponse,
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
