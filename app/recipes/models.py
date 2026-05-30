import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name              = Column(String(200), nullable=False)
    description       = Column(Text, nullable=True)
    instructions      = Column(Text, nullable=False)
    prep_time_minutes = Column(Integer, nullable=True)
    servings          = Column(Integer, default=2)
    category          = Column(String(50), nullable=True)   # 'breakfast','lunch','dinner','snack'
    image_url         = Column(String(500), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)

    ingredients  = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan")
    interactions = relationship("RecipeInteraction", back_populates="recipe")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipe_id       = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=False)
    ingredient_name = Column(String(100), nullable=False)
    quantity        = Column(Numeric(10, 2), nullable=True)
    unit            = Column(String(20), nullable=True)

    recipe = relationship("Recipe", back_populates="ingredients")


class RecipeInteraction(Base):
    __tablename__ = "recipe_interactions"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id           = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recipe_id         = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=False)
    action            = Column(String(20), nullable=False)   # 'viewed', 'cooked'
    inventory_matches = Column(Integer, nullable=True)
    occurred_at       = Column(DateTime, default=datetime.utcnow)

    recipe = relationship("Recipe", back_populates="interactions")


class RecipeFavorite(Base):
    """T3.6 — Recipes marked as favorite by a user (idempotent per user+recipe)."""
    __tablename__ = "recipe_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_recipe_favorites_user_recipe"),
    )

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    recipe_id     = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=False, index=True)
    favorited_at  = Column(DateTime, default=datetime.utcnow, nullable=False)

    recipe = relationship("Recipe")
