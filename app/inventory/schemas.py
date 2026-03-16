from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, UUID4, field_validator, model_validator


# ── Entrada ─────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    name: str
    category: Optional[str] = None
    quantity: Decimal = Decimal("1")
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    purchase_date: date
    expiry_date: date
    notes: Optional[str] = None

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

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("El precio unitario no puede ser negativo.")
        return v

    @model_validator(mode="after")
    def expiry_after_purchase(self) -> "ItemCreate":
        if self.expiry_date <= self.purchase_date:
            raise ValueError(
                "La fecha de vencimiento debe ser posterior a la fecha de compra."
            )
        return self


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None

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

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("El precio unitario no puede ser negativo.")
        return v


class ItemDiscard(BaseModel):
    reason: Literal["expired", "over_purchase", "bad_storage", "other"]
    quantity: Optional[Decimal] = None  # None = descartar todo el stock restante

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("La cantidad a descartar debe ser mayor a 0.")
        return v


# ── Salida ───────────────────────────────────────────────────────────────────

class ItemResponse(BaseModel):
    id: UUID4
    name: str
    category: Optional[str]
    quantity: Decimal
    unit: Optional[str]
    unit_price: Optional[Decimal]
    purchase_date: date
    expiry_date: date
    status: str
    days_remaining: int      # viene del @property del modelo
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    total: int
