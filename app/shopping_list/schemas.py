from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


SourceType = Literal["manual", "consumed", "recipe"]


# ── Entrada ─────────────────────────────────────────────────────────────────

class ShoppingItemCreate(BaseModel):
    id: str                            # el cliente envía el id (formato 'sl_<timestamp>')
    name: str
    category: str = "Otros"
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    purchased: bool = False
    source: SourceType = "manual"
    source_ref: Optional[str] = None

    @field_validator("id")
    @classmethod
    def id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El id no puede estar vacío.")
        return v.strip()

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("El nombre no puede estar vacío.")
        return v.strip()

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        return v


class ShoppingItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    purchased: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("El nombre no puede estar vacío.")
        return v.strip() if v else v

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("La cantidad debe ser mayor a 0.")
        return v


# ── Salida ───────────────────────────────────────────────────────────────────

class ShoppingItemResponse(BaseModel):
    id: str
    name: str
    category: str
    quantity: Decimal
    unit: Optional[str]
    purchased: bool
    source: str
    source_ref: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
