from datetime import date
from decimal import Decimal
import logging
import uuid

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem, InventoryEvent
from app.inventory.schemas import ItemCreate, ItemUpdate, ItemDiscard, BulkItemsCreate
from app.common.exceptions import AppException, ErrorCode

logger = logging.getLogger(__name__)


def get_items(db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 20):
    base = db.query(InventoryItem).filter(
        and_(
            InventoryItem.user_id == user_id,
            InventoryItem.status == "active",
        )
    )
    total = base.count()
    items = base.order_by(InventoryItem.expiry_date.asc()).offset(skip).limit(limit).all()
    return items, total


def get_expiring_items(db: Session, user_id: uuid.UUID, days: int = 3):
    """Retorna ítems que vencen en los próximos N días — alimenta las alertas."""
    today = date.today()
    return (
        db.query(InventoryItem)
        .filter(
            and_(
                InventoryItem.user_id == user_id,
                InventoryItem.status == "active",
                InventoryItem.expiry_date <= date.fromordinal(today.toordinal() + days),
            )
        )
        .order_by(InventoryItem.expiry_date.asc())
        .all()
    )


def create_item(db: Session, user_id: uuid.UUID, data: ItemCreate) -> InventoryItem:
    # La validación de fechas ya ocurre en el schema (model_validator) → llega aquí limpio
    item = InventoryItem(user_id=user_id, **data.model_dump())
    db.add(item)
    db.flush()  # obtiene el id sin hacer commit todavía

    event = InventoryEvent(
        user_id=user_id,
        item_id=item.id,
        event_type="registered",
        quantity=data.quantity,
        unit_price=data.unit_price,
    )
    db.add(event)
    db.commit()
    db.refresh(item)

    _dispatch_immediate_expiry(db, user_id, item)
    return item


def bulk_create_items(db: Session, user_id: uuid.UUID, data: BulkItemsCreate) -> list[InventoryItem]:
    """Crea múltiples items en una sola transacción — ideal para escaneo OCR de recibos."""
    created_items: list[InventoryItem] = []

    for item_data in data.items:
        item = InventoryItem(user_id=user_id, **item_data.model_dump())
        db.add(item)
        db.flush()

        event = InventoryEvent(
            user_id=user_id,
            item_id=item.id,
            event_type="registered",
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
        )
        db.add(event)
        created_items.append(item)

    db.commit()
    for item in created_items:
        db.refresh(item)
        _dispatch_immediate_expiry(db, user_id, item)
    return created_items


def _dispatch_immediate_expiry(db: Session, user_id: uuid.UUID, item: InventoryItem) -> None:
    """Dispara el push de expiración apenas se registra el item, en lugar de
    esperar al scheduler horario. process_item_expiry_notification ya valida
    threshold del usuario, dedupe y quiet hours, así que es seguro llamarlo
    siempre. Cualquier fallo se loggea sin romper el create."""
    try:
        from app.notifications.service import process_item_expiry_notification
        process_item_expiry_notification(
            db=db, user_id=user_id, item=item, source="item_registered"
        )
    except Exception as exc:
        logger.warning(
            "immediate_expiry_dispatch_failed item_id=%s err=%s", item.id, exc
        )


def update_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, data: ItemUpdate):
    item = _get_item_or_404(db, user_id, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def consume_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID):
    item = _get_item_or_404(db, user_id, item_id)
    _assert_active(item)

    item.status = "consumed"
    event = InventoryEvent(
        user_id=user_id,
        item_id=item.id,
        event_type="consumed",
        quantity=item.quantity,
        unit_price=item.unit_price,
    )
    db.add(event)
    db.commit()
    db.refresh(item)
    return item


def discard_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID, data: ItemDiscard):
    item = _get_item_or_404(db, user_id, item_id)
    _assert_active(item)

    # None significa "descartar todo"; cantidad explícita = descarte parcial
    discard_qty: Decimal = data.quantity if data.quantity is not None else item.quantity

    if discard_qty > item.quantity:
        raise AppException(
            status_code=400,
            code=ErrorCode.QUANTITY_EXCEEDS_STOCK,
            message=(
                f"No puedes descartar {discard_qty} — "
                f"solo tienes {item.quantity} disponible."
            ),
        )

    item.quantity = item.quantity - discard_qty

    # Marcar como descartado solo si ya no queda stock
    if item.quantity <= 0:
        item.status = "discarded"

    event = InventoryEvent(
        user_id=user_id,
        item_id=item.id,
        event_type="discarded",
        reason=data.reason,
        quantity=discard_qty,        # cantidad real descartada, no la del item
        unit_price=item.unit_price,
    )
    db.add(event)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID):
    item = _get_item_or_404(db, user_id, item_id)
    db.delete(item)
    db.commit()


# ── Helpers privados ────────────────────────────────────────────────────────


def _get_item_or_404(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> InventoryItem:
    """Busca un ítem verificando que pertenezca al usuario autenticado.
    Devuelve 404 tanto si no existe como si pertenece a otro usuario
    (evita enumerar ítems ajenos)."""
    item = (
        db.query(InventoryItem)
        .filter(
            and_(
                InventoryItem.id == item_id,
                InventoryItem.user_id == user_id,
            )
        )
        .first()
    )
    if not item:
        raise AppException(
            status_code=404,
            code=ErrorCode.ITEM_NOT_FOUND,
            message="El producto no existe en tu inventario.",
        )
    return item


def _assert_active(item: InventoryItem) -> None:
    """Lanza 409 si el ítem ya fue consumido o descartado."""
    if item.status != "active":
        label = "consumido" if item.status == "consumed" else "descartado"
        raise AppException(
            status_code=409,
            code=ErrorCode.ITEM_NOT_ACTIVE,
            message=f"Este ítem ya fue {label} y no puede modificarse.",
        )
