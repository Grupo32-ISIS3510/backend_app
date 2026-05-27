import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.recipes import service as recipe_service
from app.recipes.schemas import (
    RecipeDetailResponse,
    RecipeSummaryResponse,
    RecipeListResponse,
    RecipeInteractRequest,
    RecipeFavoriteItem,
    RecipeFavoritesListResponse,
)

router = APIRouter(prefix="/api/v1/recipes", tags=["Recetas"])


# IMPORTANTE: las rutas exactas (/suggestions, /seed) deben declararse ANTES
# del parámetro dinámico (/{recipe_id}) para que FastAPI no las interprete como UUID.

@router.get("/suggestions", response_model=list[RecipeSummaryResponse])
def get_suggestions(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recetas sugeridas según los ítems del inventario más próximos a vencer."""
    return recipe_service.get_suggestions(db, current_user.id, limit)


@router.post("/seed", status_code=201)
def seed(db: Session = Depends(get_db)):
    """Admin endpoint (sin autenticación) — inserta recetas de demo si la tabla está vacía."""
    count = recipe_service.seed_recipes(db)
    if count == 0:
        return {"status": "success", "message": "Las recetas ya estaban cargadas."}
    return {"status": "success", "message": f"{count} recetas insertadas correctamente."}


# ── T3.6 Favoritos ──────────────────────────────────────────────────────────
# IMPORTANTE: /favorites debe ir ANTES de /{recipe_id} para que no se interprete como UUID.

@router.get("/favorites", response_model=RecipeFavoritesListResponse)
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista las recetas que el usuario marcó como favoritas (más recientes primero)."""
    return recipe_service.list_favorites(db, current_user.id)


@router.get("/", response_model=RecipeListResponse)
def list_recipes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista todas las recetas con paginado."""
    return recipe_service.list_recipes(db, current_user.id, skip, limit)


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
def get_recipe(
    recipe_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalle de una receta con ingredientes y coincidencias del inventario."""
    return recipe_service.get_recipe(db, current_user.id, recipe_id)


@router.post("/{recipe_id}/interact", status_code=201)
def interact(
    recipe_id: uuid.UUID,
    data: RecipeInteractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra una interacción ('viewed' o 'cooked'). Al cocinar, consume los ítems coincidentes."""
    recipe_service.interact(db, current_user.id, recipe_id, data.action)
    return {"status": "success", "message": f"Interacción '{data.action}' registrada."}


@router.post("/{recipe_id}/favorite", response_model=RecipeFavoriteItem, status_code=201)
def add_favorite(
    recipe_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marca la receta como favorita. Idempotente (si ya estaba, devuelve la existente)."""
    return recipe_service.add_favorite(db, current_user.id, recipe_id)


@router.delete("/{recipe_id}/favorite", status_code=204)
def remove_favorite(
    recipe_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quita la receta de favoritos. No falla si no estaba marcada."""
    recipe_service.remove_favorite(db, current_user.id, recipe_id)
    return None
