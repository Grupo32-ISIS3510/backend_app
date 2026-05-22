from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.inventory import service as inventory_service
from app.inventory.schemas import (
    ItemCreate,
    ItemUpdate,
    ItemDiscard,
    ItemResponse,
    ItemListResponse,
    BulkItemsCreate,
)

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventario"])


@router.get("", response_model=ItemListResponse)
def get_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items, total = inventory_service.get_items(db, current_user.id, skip, limit)
    return ItemListResponse(items=items, total=total)


@router.get("/expiring", response_model=list[ItemResponse])
def get_expiring(
    days: int = Query(3, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return inventory_service.get_expiring_items(db, current_user.id, days)


@router.post("", response_model=ItemResponse, status_code=201)
def create_item(
    data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return inventory_service.create_item(db, current_user.id, data)


@router.post("/bulk", response_model=list[ItemResponse], status_code=201)
def bulk_create_items(
    data: BulkItemsCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return inventory_service.bulk_create_items(db, current_user.id, data)


@router.put("/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: uuid.UUID,
    data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return inventory_service.update_item(db, current_user.id, item_id, data)


@router.patch("/{item_id}/consume", response_model=ItemResponse)
def consume_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return inventory_service.consume_item(db, current_user.id, item_id)


@router.patch("/{item_id}/discard", response_model=ItemResponse)
def discard_item(
    item_id: uuid.UUID,
    data: ItemDiscard,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return inventory_service.discard_item(db, current_user.id, item_id, data)


@router.delete("/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inventory_service.delete_item(db, current_user.id, item_id)