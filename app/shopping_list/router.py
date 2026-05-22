from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.shopping_list import service as shopping_service
from app.shopping_list.schemas import (
    ShoppingItemCreate,
    ShoppingItemUpdate,
    ShoppingItemResponse,
)

router = APIRouter(prefix="/api/v1/shopping-list", tags=["Lista de compras"])


@router.get("", response_model=list[ShoppingItemResponse])
def get_shopping_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return shopping_service.list_items(db, current_user.id)


@router.post("", response_model=ShoppingItemResponse, status_code=201)
def create_shopping_item(
    data: ShoppingItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return shopping_service.create_item(db, current_user.id, data)


@router.put("/{item_id}", response_model=ShoppingItemResponse)
def update_shopping_item(
    item_id: str,
    data: ShoppingItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return shopping_service.update_item(db, current_user.id, item_id, data)


@router.delete("/{item_id}", status_code=204)
def delete_shopping_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    shopping_service.delete_item(db, current_user.id, item_id)


@router.delete("/purchased/all", status_code=200)
def clear_purchased(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Elimina de la lista todos los items marcados como comprados."""
    deleted = shopping_service.clear_purchased(db, current_user.id)
    return {"deleted": deleted}
