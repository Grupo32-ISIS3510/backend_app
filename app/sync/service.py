from datetime import datetime
import uuid

from sqlalchemy.orm import Session

from app.sync.models import SyncLog
from app.sync.schemas import SyncChange, SyncPushRequest, SyncPushResponse, SyncPullResponse
from app.inventory.models import InventoryItem


def push_changes(
    db: Session, user_id: uuid.UUID, request: SyncPushRequest
) -> SyncPushResponse:
    """Recibe cambios del cliente, detecta conflictos y aplica los no conflictivos."""
    processed: list[str] = []
    conflicts: list[str] = []

    for change in request.changes:
        # Conflicto: existe un SyncLog del servidor más reciente que el cliente para esa entidad.
        # Estrategia de resolución: last-write-wins (el servidor gana si su versión es más nueva).
        recent_server_log = (
            db.query(SyncLog)
            .filter(
                SyncLog.user_id == user_id,
                SyncLog.entity_id == change.entity_id,
                SyncLog.server_timestamp > change.client_timestamp,
                SyncLog.is_conflict == False,
            )
            .order_by(SyncLog.server_timestamp.desc())
            .first()
        )

        is_conflict = recent_server_log is not None

        if not is_conflict:
            _apply_change(db, user_id, change)
            processed.append(str(change.entity_id))
        else:
            conflicts.append(str(change.entity_id))

        db.add(SyncLog(
            user_id=user_id,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            operation=change.operation,
            payload=change.payload,
            client_timestamp=change.client_timestamp,
            is_conflict=is_conflict,
        ))

    db.commit()
    return SyncPushResponse(
        processed=processed,
        conflicts=conflicts,
        server_timestamp=datetime.utcnow(),
    )


def pull_changes(
    db: Session, user_id: uuid.UUID, since: datetime
) -> SyncPullResponse:
    """Retorna todos los cambios del servidor posteriores al timestamp dado."""
    logs = (
        db.query(SyncLog)
        .filter(
            SyncLog.user_id == user_id,
            SyncLog.server_timestamp > since,
            SyncLog.is_conflict == False,
        )
        .order_by(SyncLog.server_timestamp.asc())
        .all()
    )

    changes = [
        SyncChange(
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            operation=log.operation,
            payload=log.payload,
            client_timestamp=log.server_timestamp,  # el cliente usa el timestamp del servidor
        )
        for log in logs
    ]

    server_timestamp = logs[-1].server_timestamp if logs else datetime.utcnow()

    return SyncPullResponse(
        changes=changes,
        server_timestamp=server_timestamp,
        has_more=False,  # MVP: sin paginación en pull
    )


# ── Helper privado ────────────────────────────────────────────────────────────

def _apply_change(db: Session, user_id: uuid.UUID, change: SyncChange) -> None:
    """Aplica un cambio del cliente al modelo ORM correspondiente.
    Solo soporta entity_type='inventory_item' en esta versión."""
    if change.entity_type != "inventory_item":
        return

    if change.operation == "create":
        # Idempotencia: no duplicar si ya fue procesado antes
        existing = db.query(InventoryItem).filter(
            InventoryItem.id == change.entity_id
        ).first()
        if not existing:
            # Filtrar campos que el cliente no debe poder fijar
            safe_payload = {
                k: v for k, v in change.payload.items()
                if k not in ("id", "user_id", "created_at", "updated_at")
            }
            db.add(InventoryItem(
                id=change.entity_id,
                user_id=user_id,
                **safe_payload,
            ))

    elif change.operation == "update":
        item = db.query(InventoryItem).filter(
            InventoryItem.id == change.entity_id,
            InventoryItem.user_id == user_id,
        ).first()
        if item:
            for key, value in change.payload.items():
                if hasattr(item, key) and key not in ("id", "user_id", "created_at"):
                    setattr(item, key, value)

    elif change.operation == "delete":
        item = db.query(InventoryItem).filter(
            InventoryItem.id == change.entity_id,
            InventoryItem.user_id == user_id,
        ).first()
        if item:
            db.delete(item)
