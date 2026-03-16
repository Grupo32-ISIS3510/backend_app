from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import Date, cast, extract, func
from sqlalchemy.orm import Session

from app.inventory.models import InventoryEvent, InventoryItem
from app.recipes.models import RecipeInteraction
from app.analytics.schemas import (
    DashboardResponse,
    SavingsResponse,
    UserSegmentResponse,
    WasteSummaryResponse,
    WasteTrendItem,
)


def get_monthly_savings(
    db: Session, user_id: uuid.UUID, month: int, year: int
) -> SavingsResponse:
    """Dinero 'rescatado' (consumido ≤ 3 días antes de vencer) vs perdido (descartado)."""

    # Rescatado: ítems consumed donde (expiry_date − occurred_at::date) ≤ 3
    # En PostgreSQL, date − date devuelve integer (días).
    saved_raw = (
        db.query(
            func.coalesce(
                func.sum(InventoryEvent.quantity * InventoryEvent.unit_price),
                Decimal("0"),
            )
        )
        .join(InventoryItem, InventoryEvent.item_id == InventoryItem.id)
        .filter(
            InventoryEvent.user_id == user_id,
            InventoryEvent.event_type == "consumed",
            extract("month", InventoryEvent.occurred_at) == month,
            extract("year", InventoryEvent.occurred_at) == year,
            (InventoryItem.expiry_date - cast(InventoryEvent.occurred_at, Date)) <= 3,
        )
        .scalar()
    )

    # Perdido: ítems discarded en el mes
    wasted_raw = (
        db.query(
            func.coalesce(
                func.sum(InventoryEvent.quantity * InventoryEvent.unit_price),
                Decimal("0"),
            )
        )
        .filter(
            InventoryEvent.user_id == user_id,
            InventoryEvent.event_type == "discarded",
            extract("month", InventoryEvent.occurred_at) == month,
            extract("year", InventoryEvent.occurred_at) == year,
        )
        .scalar()
    )

    return SavingsResponse(
        saved_cop=Decimal(str(saved_raw or 0)),
        wasted_cop=Decimal(str(wasted_raw or 0)),
        period=f"{year}-{month:02d}",
    )


def get_waste_trends(
    db: Session, user_id: uuid.UUID, months: int
) -> list[WasteTrendItem]:
    """Ítems descartados agrupados por mes y categoría en los últimos N meses."""
    cutoff = datetime.utcnow() - timedelta(days=months * 30)

    rows = (
        db.query(
            func.to_char(InventoryEvent.occurred_at, "YYYY-MM").label("month"),
            InventoryItem.category.label("category"),
            func.count(InventoryEvent.id).label("items_discarded"),
            func.coalesce(
                func.sum(InventoryEvent.quantity * InventoryEvent.unit_price),
                Decimal("0"),
            ).label("value_lost_cop"),
        )
        .join(InventoryItem, InventoryEvent.item_id == InventoryItem.id)
        .filter(
            InventoryEvent.user_id == user_id,
            InventoryEvent.event_type == "discarded",
            InventoryEvent.occurred_at >= cutoff,
        )
        .group_by(
            func.to_char(InventoryEvent.occurred_at, "YYYY-MM"),
            InventoryItem.category,
        )
        .order_by(func.to_char(InventoryEvent.occurred_at, "YYYY-MM"))
        .all()
    )

    return [
        WasteTrendItem(
            month=row.month,
            category=row.category,
            items_discarded=row.items_discarded,
            value_lost_cop=Decimal(str(row.value_lost_cop or 0)),
        )
        for row in rows
    ]


def get_waste_summary(db: Session, user_id: uuid.UUID) -> WasteSummaryResponse:
    """Resumen histórico de consumo vs descarte, racha sin desperdiciar."""

    total_consumed = (
        db.query(func.count(InventoryEvent.id))
        .filter(InventoryEvent.user_id == user_id, InventoryEvent.event_type == "consumed")
        .scalar() or 0
    )

    total_discarded = (
        db.query(func.count(InventoryEvent.id))
        .filter(InventoryEvent.user_id == user_id, InventoryEvent.event_type == "discarded")
        .scalar() or 0
    )

    # Categoría más desperdiciada
    most_wasted_cat_row = (
        db.query(
            InventoryItem.category,
            func.count(InventoryEvent.id).label("cnt"),
        )
        .join(InventoryEvent, InventoryEvent.item_id == InventoryItem.id)
        .filter(InventoryEvent.user_id == user_id, InventoryEvent.event_type == "discarded")
        .group_by(InventoryItem.category)
        .order_by(func.count(InventoryEvent.id).desc())
        .first()
    )

    # Ítem más frecuentemente descartado
    most_discarded_item_row = (
        db.query(
            InventoryItem.name,
            func.count(InventoryEvent.id).label("cnt"),
        )
        .join(InventoryEvent, InventoryEvent.item_id == InventoryItem.id)
        .filter(InventoryEvent.user_id == user_id, InventoryEvent.event_type == "discarded")
        .group_by(InventoryItem.name)
        .order_by(func.count(InventoryEvent.id).desc())
        .first()
    )

    # Racha: días consecutivos sin desperdiciar
    last_discard_ts = (
        db.query(func.max(InventoryEvent.occurred_at))
        .filter(InventoryEvent.user_id == user_id, InventoryEvent.event_type == "discarded")
        .scalar()
    )

    if last_discard_ts:
        streak = max(0, (datetime.utcnow().date() - last_discard_ts.date()).days)
    else:
        # Nunca descartó — racha desde el primer evento registrado
        first_event_ts = (
            db.query(func.min(InventoryEvent.occurred_at))
            .filter(InventoryEvent.user_id == user_id)
            .scalar()
        )
        streak = (datetime.utcnow().date() - first_event_ts.date()).days if first_event_ts else 0

    return WasteSummaryResponse(
        total_consumed=total_consumed,
        total_discarded=total_discarded,
        most_wasted_category=most_wasted_cat_row.category if most_wasted_cat_row else None,
        most_discarded_item=most_discarded_item_row.name if most_discarded_item_row else None,
        no_waste_streak_days=streak,
    )


def get_user_segment(db: Session, user_id: uuid.UUID) -> UserSegmentResponse:
    """Clasifica al usuario según su comportamiento en los últimos 30 días."""
    since = datetime.utcnow() - timedelta(days=30)

    recipes_cooked = (
        db.query(func.count(RecipeInteraction.id))
        .filter(
            RecipeInteraction.user_id == user_id,
            RecipeInteraction.action == "cooked",
            RecipeInteraction.occurred_at >= since,
        )
        .scalar() or 0
    )

    # NotificationInteraction no existe en esta versión del MVP;
    # open_rate se reserva para cuando se implemente el tracking de notificaciones.
    open_rate: float = 0.0

    if open_rate >= 0.6 and recipes_cooked >= 3:
        segment = "proactive"
    elif open_rate < 0.2 and recipes_cooked == 0:
        segment = "passive"
    else:
        segment = "neutral"

    return UserSegmentResponse(
        segment=segment,
        recipes_cooked_last_30_days=recipes_cooked,
        open_rate=open_rate,
    )


def get_dashboard(
    db: Session, user_id: uuid.UUID, month: int, year: int
) -> DashboardResponse:
    """Agrega todas las métricas en un solo response para el cliente móvil."""
    return DashboardResponse(
        savings=get_monthly_savings(db, user_id, month, year),
        waste_summary=get_waste_summary(db, user_id),
        segment=get_user_segment(db, user_id),
    )
