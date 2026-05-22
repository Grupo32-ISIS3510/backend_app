import uuid
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.shopping_list.models import ShoppingItem
from app.shopping_list.schemas import ShoppingItemCreate, ShoppingItemUpdate
from app.common.exceptions import AppException, ErrorCode


def list_items(db: Session, user_id: uuid.UUID) -> list[ShoppingItem]:
    """Lista los items del usuario ordenando primero los pendientes,
    luego los comprados, dentro de cada grupo por más recientes."""
    return (
        db.query(ShoppingItem)
        .filter(ShoppingItem.user_id == user_id)
        .order_by(ShoppingItem.purchased.asc(), ShoppingItem.created_at.desc())
        .all()
    )


def create_item(db: Session, user_id: uuid.UUID, data: ShoppingItemCreate) -> ShoppingItem:
    # Upsert por id: si el cliente reintenta tras un fallo offline, no duplicamos.
    existing = (
        db.query(ShoppingItem)
        .filter(and_(ShoppingItem.id == data.id, ShoppingItem.user_id == user_id))
        .first()
    )
    if existing:
        for field, value in data.model_dump().items():
            if field != "id":
                setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    item = ShoppingItem(user_id=user_id, **data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(
    db: Session,
    user_id: uuid.UUID,
    item_id: str,
    data: ShoppingItemUpdate,
) -> ShoppingItem:
    item = _get_item_or_404(db, user_id, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, user_id: uuid.UUID, item_id: str) -> None:
    item = _get_item_or_404(db, user_id, item_id)
    db.delete(item)
    db.commit()


def clear_purchased(db: Session, user_id: uuid.UUID) -> int:
    """Elimina todos los items marcados como comprados.
    Retorna la cantidad borrada."""
    count = (
        db.query(ShoppingItem)
        .filter(
            and_(
                ShoppingItem.user_id == user_id,
                ShoppingItem.purchased.is_(True),
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return count


# ── Helpers privados ────────────────────────────────────────────────────────


def _get_item_or_404(db: Session, user_id: uuid.UUID, item_id: str) -> ShoppingItem:
    """Igual que en inventory: 404 también cuando pertenece a otro usuario."""
    item = (
        db.query(ShoppingItem)
        .filter(and_(ShoppingItem.id == item_id, ShoppingItem.user_id == user_id))
        .first()
    )
    if not item:
        raise AppException(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="El item de la lista de compras no existe.",
        )
    return item
