from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, UUID4


# ── Entrada ─────────────────────────────────────────────────────────────────

class RecipeInteractRequest(BaseModel):
    action: Literal["viewed", "cooked"]


# ── Salida ───────────────────────────────────────────────────────────────────

class RecipeIngredientResponse(BaseModel):
    id: UUID4
    ingredient_name: str
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class RecipeDetailResponse(BaseModel):
    """Vista completa de una receta — incluye ingredientes y coincidencias del inventario."""
    id: UUID4
    name: str
    description: Optional[str] = None
    instructions: str
    prep_time_minutes: Optional[int] = None
    servings: int
    category: Optional[str] = None
    image_url: Optional[str] = None
    ingredients: list[RecipeIngredientResponse]
    inventory_matches: int    # cuántos ingredientes tiene el usuario en stock activo
    created_at: datetime

    class Config:
        from_attributes = True


class RecipeSummaryResponse(BaseModel):
    """Vista resumida para listados y sugerencias."""
    id: UUID4
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    prep_time_minutes: Optional[int] = None
    servings: int
    image_url: Optional[str] = None
    inventory_matches: int

    class Config:
        from_attributes = True


class RecipeListResponse(BaseModel):
    items: list[RecipeSummaryResponse]
    total: int
