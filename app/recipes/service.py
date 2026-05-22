from datetime import datetime, date
from decimal import Decimal
import uuid

from sqlalchemy.orm import Session, joinedload

from app.recipes.models import Recipe, RecipeIngredient, RecipeInteraction
from app.recipes.schemas import (
    RecipeDetailResponse,
    RecipeSummaryResponse,
    RecipeIngredientResponse,
    RecipeListResponse,
)
from app.inventory.models import InventoryItem, InventoryEvent
from app.common.exceptions import AppException, ErrorCode


# ── Helpers privados ─────────────────────────────────────────────────────────

def _get_active_items(db: Session, user_id: uuid.UUID) -> list[InventoryItem]:
    return (
        db.query(InventoryItem)
        .filter(InventoryItem.user_id == user_id, InventoryItem.status == "active")
        .all()
    )


def _item_matches_ingredient(item_name: str, ingredient_name: str) -> bool:
    """Coincidencia bidireccional por substring (case-insensitive).
    Ejemplo: item 'leche' coincide con ingrediente 'leche entera'."""
    a, b = item_name.lower(), ingredient_name.lower()
    return a in b or b in a


def _compute_matches(recipe: Recipe, item_names: set[str]) -> int:
    """Cuenta cuántos ingredientes de la receta están en el set de nombres de ítems."""
    return sum(
        1
        for ing in recipe.ingredients
        if any(_item_matches_ingredient(item_n, ing.ingredient_name) for item_n in item_names)
    )


def _build_summary(recipe: Recipe, matches: int) -> RecipeSummaryResponse:
    return RecipeSummaryResponse(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        category=recipe.category,
        prep_time_minutes=recipe.prep_time_minutes,
        servings=recipe.servings,
        image_url=recipe.image_url,
        inventory_matches=matches,
    )


def _build_detail(recipe: Recipe, matches: int) -> RecipeDetailResponse:
    return RecipeDetailResponse(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        instructions=recipe.instructions,
        prep_time_minutes=recipe.prep_time_minutes,
        servings=recipe.servings,
        category=recipe.category,
        image_url=recipe.image_url,
        ingredients=[
            RecipeIngredientResponse(
                id=i.id,
                ingredient_name=i.ingredient_name,
                quantity=i.quantity,
                unit=i.unit,
            )
            for i in recipe.ingredients
        ],
        inventory_matches=matches,
        created_at=recipe.created_at,
    )


def _get_recipe_or_404(db: Session, recipe_id: uuid.UUID) -> Recipe:
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .filter(Recipe.id == recipe_id)
        .first()
    )
    if not recipe:
        raise AppException(
            status_code=404,
            code=ErrorCode.NOT_FOUND,
            message="Receta no encontrada.",
        )
    return recipe


# ── Funciones públicas ────────────────────────────────────────────────────────

def get_suggestions(
    db: Session, user_id: uuid.UUID, limit: int = 10
) -> list[RecipeSummaryResponse]:
    """Retorna las top N recetas priorizando las que usan ingredientes próximos a vencer."""
    active_items = _get_active_items(db, user_id)

    # Items próximos a vencer (≤ 5 días) son los que elevan el score de la receta
    expiring_names = {
        item.name for item in active_items if item.days_remaining <= 5
    }
    all_active_names = {item.name for item in active_items}

    recipes = (
        db.query(Recipe)
        .options(joinedload(Recipe.ingredients))
        .all()
    )

    # Puntaje = ingredientes que coinciden con ítems por vencer
    scored: list[tuple[int, Recipe]] = [
        (_compute_matches(r, expiring_names), r)
        for r in recipes
    ]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        _build_summary(recipe, _compute_matches(recipe, all_active_names))
        for _, recipe in scored[:limit]
    ]


def get_recipe(
    db: Session, user_id: uuid.UUID, recipe_id: uuid.UUID
) -> RecipeDetailResponse:
    recipe = _get_recipe_or_404(db, recipe_id)
    active_names = {item.name for item in _get_active_items(db, user_id)}
    return _build_detail(recipe, _compute_matches(recipe, active_names))


def interact(
    db: Session, user_id: uuid.UUID, recipe_id: uuid.UUID, action: str
) -> None:
    recipe = _get_recipe_or_404(db, recipe_id)

    matches = None
    if action == "cooked":
        active_items = _get_active_items(db, user_id)
        active_names = {item.name for item in active_items}
        matches = _compute_matches(recipe, active_names)

        consumed_ids: set[uuid.UUID] = set()
        for ing in recipe.ingredients:
            for item in active_items:
                if item.id not in consumed_ids and _item_matches_ingredient(item.name, ing.ingredient_name):
                    item.status = "consumed"
                    consumed_ids.add(item.id)
                    event = InventoryEvent(
                        user_id=user_id,
                        item_id=item.id,
                        event_type="consumed",
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                    )
                    db.add(event)

    interaction = RecipeInteraction(
        user_id=user_id,
        recipe_id=recipe.id,
        action=action,
        inventory_matches=matches,
    )
    db.add(interaction)
    db.commit()


def list_recipes(
    db: Session, user_id: uuid.UUID, skip: int = 0, limit: int = 20
) -> RecipeListResponse:
    all_active_names = {item.name for item in _get_active_items(db, user_id)}

    base = db.query(Recipe).options(joinedload(Recipe.ingredients))
    total = db.query(Recipe).count()
    recipes = base.offset(skip).limit(limit).all()

    return RecipeListResponse(
        items=[_build_summary(r, _compute_matches(r, all_active_names)) for r in recipes],
        total=total,
    )


def seed_recipes(db: Session) -> int:
    """Inserta recetas de demo si la tabla está vacía. Retorna el número de recetas insertadas."""
    if db.query(Recipe).count() > 0:
        return 0

    recipes_data = [
        {
            "name": "Arroz con leche",
            "description": "Postre cremoso tradicional con arroz y leche.",
            "instructions": "1. Cocinar el arroz en agua. 2. Agregar leche y azúcar. 3. Cocinar a fuego lento 20 min. 4. Añadir canela y servir.",
            "prep_time_minutes": 30,
            "servings": 4,
            "category": "snack",
            "ingredients": [("arroz", Decimal("1"), "taza"), ("leche", Decimal("2"), "tazas"), ("azúcar", Decimal("3"), "cdas"), ("canela", None, "al gusto")],
        },
        {
            "name": "Avena con frutas",
            "description": "Desayuno nutritivo con avena y frutas frescas.",
            "instructions": "1. Hervir la leche. 2. Agregar avena y cocinar 5 min. 3. Agregar miel. 4. Servir con plátano en rodajas.",
            "prep_time_minutes": 10,
            "servings": 1,
            "category": "breakfast",
            "ingredients": [("avena", Decimal("0.5"), "taza"), ("leche", Decimal("1"), "taza"), ("plátano", Decimal("1"), "unidad"), ("miel", Decimal("1"), "cda")],
        },
        {
            "name": "Ensalada César",
            "description": "Clásica ensalada César con pollo a la plancha.",
            "instructions": "1. Cortar la lechuga. 2. Grillar el pollo y cortarlo en tiras. 3. Mezclar con queso parmesano. 4. Aliñar con aderezo César y jugo de limón.",
            "prep_time_minutes": 20,
            "servings": 2,
            "category": "lunch",
            "ingredients": [("lechuga", Decimal("1"), "cabeza"), ("pollo", Decimal("200"), "g"), ("queso parmesano", Decimal("50"), "g"), ("limón", Decimal("1"), "unidad")],
        },
        {
            "name": "Sopa de pollo",
            "description": "Sopa reconfortante con pollo y vegetales.",
            "instructions": "1. Hervir el pollo con agua y sal. 2. Agregar zanahoria y papa en cubos. 3. Sofreír cebolla y ajo. 4. Mezclar todo y cocinar 30 min.",
            "prep_time_minutes": 45,
            "servings": 4,
            "category": "lunch",
            "ingredients": [("pollo", Decimal("500"), "g"), ("zanahoria", Decimal("2"), "unidades"), ("papa", Decimal("3"), "unidades"), ("cebolla", Decimal("1"), "unidad"), ("ajo", Decimal("2"), "dientes")],
        },
        {
            "name": "Tortilla española",
            "description": "Tortilla de patata tradicional española.",
            "instructions": "1. Pelar y cortar las papas en láminas. 2. Freír en aceite de oliva. 3. Batir huevos con sal. 4. Mezclar y cuajar en la sartén a fuego medio.",
            "prep_time_minutes": 35,
            "servings": 4,
            "category": "lunch",
            "ingredients": [("huevos", Decimal("4"), "unidades"), ("papa", Decimal("3"), "unidades"), ("cebolla", Decimal("1"), "unidad"), ("aceite", Decimal("3"), "cdas")],
        },
        {
            "name": "Pasta boloñesa",
            "description": "Pasta con salsa de carne y tomate.",
            "instructions": "1. Sofreír cebolla y ajo. 2. Agregar carne molida y dorar. 3. Añadir tomate y cocinar 20 min. 4. Servir sobre pasta cocida.",
            "prep_time_minutes": 35,
            "servings": 4,
            "category": "dinner",
            "ingredients": [("pasta", Decimal("400"), "g"), ("carne molida", Decimal("300"), "g"), ("tomate", Decimal("3"), "unidades"), ("cebolla", Decimal("1"), "unidad"), ("ajo", Decimal("3"), "dientes")],
        },
        {
            "name": "Puré de papa",
            "description": "Cremoso puré de papa con mantequilla y leche.",
            "instructions": "1. Hervir las papas peladas. 2. Escurrir y aplastar. 3. Agregar mantequilla y leche caliente. 4. Mezclar hasta obtener consistencia cremosa.",
            "prep_time_minutes": 25,
            "servings": 4,
            "category": "lunch",
            "ingredients": [("papa", Decimal("4"), "unidades"), ("mantequilla", Decimal("2"), "cdas"), ("leche", Decimal("0.5"), "taza")],
        },
        {
            "name": "Pollo al horno con ajo y limón",
            "description": "Pollo jugoso marinado con ajo, limón y hierbas.",
            "instructions": "1. Marinar el pollo con ajo, limón y aceite 30 min. 2. Hornear a 180°C por 45 min. 3. Servir con el jugo de la cocción.",
            "prep_time_minutes": 60,
            "servings": 4,
            "category": "dinner",
            "ingredients": [("pollo", Decimal("1"), "kg"), ("ajo", Decimal("4"), "dientes"), ("limón", Decimal("2"), "unidades"), ("aceite", Decimal("2"), "cdas")],
        },
        {
            "name": "Ensalada de frutas",
            "description": "Fresca ensalada de frutas de temporada.",
            "instructions": "1. Lavar y pelar las frutas. 2. Cortar en trozos medianos. 3. Mezclar en un bol. 4. Añadir jugo de naranja y servir frío.",
            "prep_time_minutes": 15,
            "servings": 3,
            "category": "snack",
            "ingredients": [("manzana", Decimal("2"), "unidades"), ("uva", Decimal("100"), "g"), ("naranja", Decimal("2"), "unidades"), ("kiwi", Decimal("2"), "unidades")],
        },
        {
            "name": "Revuelto de huevos con tomate",
            "description": "Rápido revuelto de huevos con tomate y queso.",
            "instructions": "1. Batir los huevos. 2. Sofreír tomate y cebolla. 3. Añadir huevos y revolver a fuego bajo. 4. Agregar queso rallado y servir.",
            "prep_time_minutes": 15,
            "servings": 2,
            "category": "breakfast",
            "ingredients": [("huevos", Decimal("3"), "unidades"), ("tomate", Decimal("1"), "unidad"), ("cebolla", Decimal("0.5"), "unidad"), ("queso", Decimal("30"), "g")],
        },
        {
            "name": "Sándwich de atún",
            "description": "Sándwich rápido y nutritivo con atún.",
            "instructions": "1. Mezclar atún escurrido con mayonesa. 2. Cortar tomate en rodajas. 3. Armar el sándwich con todos los ingredientes. 4. Servir frío.",
            "prep_time_minutes": 10,
            "servings": 2,
            "category": "lunch",
            "ingredients": [("atún", Decimal("1"), "lata"), ("pan", Decimal("4"), "tajadas"), ("mayonesa", Decimal("2"), "cdas"), ("tomate", Decimal("1"), "unidad")],
        },
        {
            "name": "Arroz frito con vegetales",
            "description": "Arroz salteado con huevo y vegetales al estilo asiático.",
            "instructions": "1. Cocinar el arroz el día anterior. 2. Saltear zanahoria. 3. Agregar arroz y mezclar. 4. Añadir huevo batido y salsa de soja.",
            "prep_time_minutes": 20,
            "servings": 3,
            "category": "lunch",
            "ingredients": [("arroz", Decimal("2"), "tazas"), ("zanahoria", Decimal("1"), "unidad"), ("huevos", Decimal("2"), "unidades"), ("salsa de soja", Decimal("2"), "cdas")],
        },
        {
            "name": "Crema de zanahoria",
            "description": "Suave crema de zanahoria con toque de crema de leche.",
            "instructions": "1. Sofreír cebolla. 2. Agregar zanahoria en trozos y caldo. 3. Cocinar 20 min y licuar. 4. Añadir leche y crema, ajustar sal.",
            "prep_time_minutes": 30,
            "servings": 4,
            "category": "lunch",
            "ingredients": [("zanahoria", Decimal("4"), "unidades"), ("cebolla", Decimal("1"), "unidad"), ("leche", Decimal("0.5"), "taza"), ("crema de leche", Decimal("3"), "cdas")],
        },
        {
            "name": "Batido verde energizante",
            "description": "Batido saludable con espinaca, plátano y leche.",
            "instructions": "1. Lavar la espinaca. 2. Pelar el plátano. 3. Licuar todos los ingredientes. 4. Servir inmediatamente.",
            "prep_time_minutes": 5,
            "servings": 1,
            "category": "breakfast",
            "ingredients": [("espinaca", Decimal("1"), "taza"), ("plátano", Decimal("1"), "unidad"), ("leche", Decimal("1"), "taza"), ("miel", Decimal("1"), "cda")],
        },
        {
            "name": "Quesadillas de pollo",
            "description": "Crujientes quesadillas rellenas de pollo y aguacate.",
            "instructions": "1. Cocinar el pollo desmenuzado. 2. Calentar la tortilla en sartén. 3. Agregar queso y pollo. 4. Doblar, dorar por ambos lados y servir con aguacate.",
            "prep_time_minutes": 20,
            "servings": 2,
            "category": "dinner",
            "ingredients": [("tortilla", Decimal("4"), "unidades"), ("queso", Decimal("100"), "g"), ("pollo", Decimal("200"), "g"), ("aguacate", Decimal("1"), "unidad")],
        },
    ]

    count = 0
    for data in recipes_data:
        ingredients_raw = data.pop("ingredients")
        recipe = Recipe(**data)
        db.add(recipe)
        db.flush()  # obtener recipe.id sin commit

        for ing_name, ing_qty, ing_unit in ingredients_raw:
            db.add(RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_name=ing_name,
                quantity=ing_qty,
                unit=ing_unit,
            ))
        count += 1

    db.commit()
    return count
