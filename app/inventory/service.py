from datetime import date
from decimal import Decimal
import uuid

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.inventory.models import InventoryItem, InventoryEvent
from app.inventory.schemas import ItemCreate, ItemUpdate, ItemDiscard
from app.common.exceptions import AppException, ErrorCode


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
    return item


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
