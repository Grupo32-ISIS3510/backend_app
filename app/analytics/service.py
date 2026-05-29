from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import Date, cast, extract, func, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.inventory.models import InventoryEvent, InventoryItem
from app.recipes.models import Recipe, RecipeIngredient, RecipeInteraction, RecipeFavorite
from app.telemetry.models import FeatureUsageEvent
from app.analytics.models import AnalyticsEvent
from app.analytics.schemas import (
    AnalyticsEventBatch,
    AnalyticsEventResponse,
    CategoryTrendItem,
    DashboardResponse,
    EventCount,
    EventsSummaryResponse,
    FavoriteCategoryItem,
    FavoriteIngredientItem,
    FavoritesDistributionResponse,
    MarketProductTrendsResponse,
    ProductTrendItem,
    SavingsResponse,
    SeedDemoResponse,
    SegmentPatternItem,
    SegmentsPatternsResponse,
    UserSegmentResponse,
    WasteReductionByRecipeCategoryItem,
    WasteReductionByRecipeCategoryResponse,
    WasteSummaryResponse,
    WasteTrendItem,
)


def record_events(
    db: Session, user_id: uuid.UUID, batch: AnalyticsEventBatch
) -> AnalyticsEventResponse:
    """Persiste un batch de eventos analytics enviados desde el cliente móvil."""
    objects = [
        AnalyticsEvent(
            user_id=user_id,
            event_name=evt.event_name,
            properties=evt.properties,
            session_id=evt.session_id,
            platform=evt.platform,
            app_version=evt.app_version,
            occurred_at=evt.occurred_at,
        )
        for evt in batch.events
    ]
    db.bulk_save_objects(objects)
    db.commit()
    return AnalyticsEventResponse(received=len(objects), duplicates_skipped=0)


def get_events_summary(
    db: Session, user_id: uuid.UUID, days: int
) -> EventsSummaryResponse:
    """Resumen de eventos analytics agrupados por event_name en los últimos N días."""
    since = datetime.utcnow() - timedelta(days=days)

    total = (
        db.query(func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.user_id == user_id, AnalyticsEvent.occurred_at >= since)
        .scalar() or 0
    )

    rows = (
        db.query(
            AnalyticsEvent.event_name,
            func.count(AnalyticsEvent.id).label("cnt"),
        )
        .filter(AnalyticsEvent.user_id == user_id, AnalyticsEvent.occurred_at >= since)
        .group_by(AnalyticsEvent.event_name)
        .order_by(func.count(AnalyticsEvent.id).desc())
        .all()
    )

    return EventsSummaryResponse(
        total_events=total,
        period_days=days,
        breakdown=[EventCount(event_name=r.event_name, count=r.cnt) for r in rows],
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

    notif_received = (
        db.query(func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.user_id == user_id,
            AnalyticsEvent.event_name == "notification_received",
            AnalyticsEvent.occurred_at >= since,
        )
        .scalar() or 0
    )

    notif_opened = (
        db.query(func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.user_id == user_id,
            AnalyticsEvent.event_name == "notification_opened",
            AnalyticsEvent.occurred_at >= since,
        )
        .scalar() or 0
    )

    open_rate = (notif_opened / notif_received) if notif_received > 0 else 0.0

    if open_rate >= 0.6 and recipes_cooked >= 3:
        segment = "proactive"
    elif open_rate < 0.2 and recipes_cooked == 0:
        segment = "passive"
    else:
        segment = "neutral"

    return UserSegmentResponse(
        segment=segment,
        recipes_cooked_last_30_days=recipes_cooked,
        open_rate=round(open_rate, 2),
    )


def get_dashboard(
    db: Session, user_id: uuid.UUID, month: int, year: int
) -> DashboardResponse:
    """Agrega todas las métricas en un solo response para el cliente móvil."""
    return DashboardResponse(
        savings=get_monthly_savings(db, user_id, month, year),
        waste_trends=get_waste_trends(db, user_id, months=3),
        waste_summary=get_waste_summary(db, user_id),
        segment=get_user_segment(db, user_id),
    )


# ── T4.2 seed constants ──────────────────────────────────────────────────────

_DEMO_USERS = [
    {"email": "demo_mercado_1@secondserving.demo", "full_name": "Ana García",       "location": "Bogotá"},
    {"email": "demo_mercado_2@secondserving.demo", "full_name": "Carlos Rodríguez", "location": "Medellín"},
    {"email": "demo_mercado_3@secondserving.demo", "full_name": "María López",      "location": "Cali"},
    {"email": "demo_mercado_4@secondserving.demo", "full_name": "José Martínez",    "location": "Barranquilla"},
    {"email": "demo_mercado_5@secondserving.demo", "full_name": "Laura Hernández",  "location": "Bucaramanga"},
    {"email": "demo_mercado_6@secondserving.demo", "full_name": "Diego Vargas",     "location": "Cartagena"},
]

# name → (category, unit, unit_price_cop)
_CATALOG: dict[str, tuple[str, str, int]] = {
    "Leche":            ("Lácteos",    "litros",    3_500),
    "Queso Campesino":  ("Lácteos",    "kg",       18_000),
    "Yogur Natural":    ("Lácteos",    "unidades",  4_500),
    "Mantequilla":      ("Lácteos",    "kg",       22_000),
    "Huevos":           ("Proteínas",  "unidades",    800),
    "Pechuga de Pollo": ("Proteínas",  "kg",       15_000),
    "Atún en Lata":     ("Proteínas",  "unidades",  6_500),
    "Lenteja":          ("Proteínas",  "kg",        5_200),
    "Arroz Blanco":     ("Cereales",   "kg",        4_200),
    "Avena":            ("Cereales",   "kg",        5_600),
    "Pan Tajado":       ("Cereales",   "unidades",  7_000),
    "Banano":           ("Frutas",     "kg",        2_800),
    "Manzana":          ("Frutas",     "kg",        6_500),
    "Naranja":          ("Frutas",     "kg",        3_500),
    "Tomate":           ("Verduras",   "kg",        4_500),
    "Cebolla":          ("Verduras",   "kg",        3_800),
    "Lechuga":          ("Verduras",   "unidades",  3_000),
    "Zanahoria":        ("Verduras",   "kg",        3_200),
    "Papa":             ("Verduras",   "kg",        2_800),
    "Aceite de Cocina": ("Abarrotes",  "litros",   12_000),
    "Azúcar":           ("Abarrotes",  "kg",        3_500),
    "Café Molido":      ("Bebidas",    "kg",       28_000),
    "Jugo de Naranja":  ("Bebidas",    "litros",    5_500),
    "Agua Mineral":     ("Bebidas",    "litros",    2_000),
}

_USER_PURCHASES: list[list[tuple[str, int]]] = [
    [("Leche", 3), ("Arroz Blanco", 3), ("Huevos", 3), ("Tomate", 2),
     ("Banano", 2), ("Pan Tajado", 2), ("Queso Campesino", 2), ("Café Molido", 2),
     ("Aceite de Cocina", 1), ("Lechuga", 1)],
    [("Leche", 2), ("Arroz Blanco", 2), ("Pechuga de Pollo", 3), ("Zanahoria", 2),
     ("Papa", 3), ("Lenteja", 2), ("Avena", 1), ("Manzana", 2), ("Huevos", 2)],
    [("Yogur Natural", 2), ("Leche", 2), ("Banano", 3), ("Naranja", 2),
     ("Tomate", 3), ("Cebolla", 2), ("Arroz Blanco", 2), ("Azúcar", 2), ("Manzana", 1)],
    [("Huevos", 3), ("Atún en Lata", 2), ("Arroz Blanco", 3), ("Pan Tajado", 3),
     ("Café Molido", 3), ("Jugo de Naranja", 2), ("Agua Mineral", 2), ("Leche", 1)],
    [("Leche", 3), ("Queso Campesino", 3), ("Mantequilla", 2), ("Arroz Blanco", 2),
     ("Papa", 2), ("Cebolla", 3), ("Tomate", 2), ("Manzana", 2), ("Yogur Natural", 1)],
    [("Pechuga de Pollo", 2), ("Huevos", 2), ("Arroz Blanco", 3), ("Banano", 2),
     ("Naranja", 3), ("Agua Mineral", 3), ("Aceite de Cocina", 2), ("Azúcar", 2),
     ("Lenteja", 1)],
]


# ── T4.2 ─────────────────────────────────────────────────────────────────────

def get_top_products(
    db: Session,
    top_n: int = 10,
    category: Optional[str] = None,
    min_users: int = 1,
) -> MarketProductTrendsResponse:
    """T4.2 – Productos con mayor frecuencia de consumo y tasa de recompra (cross-user)."""

    # Step 1: consumption counts aggregated across ALL users
    q = (
        db.query(
            func.lower(InventoryItem.name).label("product_name"),
            InventoryItem.category.label("category"),
            func.count(InventoryEvent.id).label("consumption_count"),
            func.count(func.distinct(InventoryEvent.user_id)).label("unique_users"),
        )
        .join(InventoryItem, InventoryEvent.item_id == InventoryItem.id)
        .filter(InventoryEvent.event_type == "consumed")
    )

    if category:
        q = q.filter(func.lower(InventoryItem.category) == category.lower())

    consumption_rows = (
        q.group_by(func.lower(InventoryItem.name), InventoryItem.category)
        .having(func.count(func.distinct(InventoryEvent.user_id)) >= min_users)
        .order_by(func.count(InventoryEvent.id).desc())
        .limit(top_n)
        .all()
    )

    if not consumption_rows:
        total_users = (
            db.query(func.count(func.distinct(InventoryEvent.user_id)))
            .filter(InventoryEvent.event_type == "consumed")
            .scalar() or 0
        )
        return MarketProductTrendsResponse(
            generated_at=datetime.utcnow(),
            total_users_analyzed=total_users,
            top_n=top_n,
            products=[],
            categories=[],
        )

    top_product_names = [r.product_name for r in consumption_rows]

    # Step 2: repurchase – users who registered the same product name ≥ 2 times
    purchase_counts = (
        db.query(
            func.lower(InventoryItem.name).label("product_name"),
            InventoryItem.user_id.label("user_id"),
            func.count(InventoryItem.id).label("times_bought"),
        )
        .filter(func.lower(InventoryItem.name).in_(top_product_names))
        .group_by(func.lower(InventoryItem.name), InventoryItem.user_id)
        .all()
    )

    buyers_by_product: dict[str, set] = defaultdict(set)
    repurchasers_by_product: dict[str, set] = defaultdict(set)
    for row in purchase_counts:
        buyers_by_product[row.product_name].add(row.user_id)
        if row.times_bought >= 2:
            repurchasers_by_product[row.product_name].add(row.user_id)

    # Step 3: build product result list
    products: list[ProductTrendItem] = []
    top_product_per_cat: dict[str, str] = {}

    for r in consumption_rows:
        pname = r.product_name
        buyers = len(buyers_by_product[pname]) or 1
        repurchasers = len(repurchasers_by_product[pname])
        avg = round(r.consumption_count / r.unique_users, 2) if r.unique_users > 0 else 0.0

        products.append(ProductTrendItem(
            product_name=pname.title(),
            category=r.category,
            consumption_count=r.consumption_count,
            unique_users=r.unique_users,
            repurchase_rate=round(repurchasers / buyers, 2),
            avg_consumption_per_user=avg,
        ))

        if r.category and r.category not in top_product_per_cat:
            top_product_per_cat[r.category] = pname.title()

    # Step 4: category-level rollup (all categories, not just top_n products)
    cat_filter = (
        db.query(
            InventoryItem.category.label("category"),
            func.count(InventoryEvent.id).label("total_consumption"),
            func.count(func.distinct(InventoryEvent.user_id)).label("unique_users"),
        )
        .join(InventoryItem, InventoryEvent.item_id == InventoryItem.id)
        .filter(
            InventoryEvent.event_type == "consumed",
            InventoryItem.category.isnot(None),
        )
        .group_by(InventoryItem.category)
        .order_by(func.count(InventoryEvent.id).desc())
        .all()
    )

    # enrich top_product_per_cat with products outside the top_n window
    if len(top_product_per_cat) < len(cat_filter):
        extra_rows = (
            db.query(
                func.lower(InventoryItem.name).label("product_name"),
                InventoryItem.category.label("category"),
                func.count(InventoryEvent.id).label("cnt"),
            )
            .join(InventoryItem, InventoryEvent.item_id == InventoryItem.id)
            .filter(InventoryEvent.event_type == "consumed", InventoryItem.category.isnot(None))
            .group_by(func.lower(InventoryItem.name), InventoryItem.category)
            .order_by(func.count(InventoryEvent.id).desc())
            .all()
        )
        for er in extra_rows:
            if er.category and er.category not in top_product_per_cat:
                top_product_per_cat[er.category] = er.product_name.title()

    categories: list[CategoryTrendItem] = [
        CategoryTrendItem(
            category=cr.category,
            total_consumption=cr.total_consumption,
            unique_users=cr.unique_users,
            top_product=top_product_per_cat.get(cr.category),
        )
        for cr in cat_filter
    ]

    total_users = (
        db.query(func.count(func.distinct(InventoryEvent.user_id)))
        .filter(InventoryEvent.event_type == "consumed")
        .scalar() or 0
    )

    return MarketProductTrendsResponse(
        generated_at=datetime.utcnow(),
        total_users_analyzed=total_users,
        top_n=top_n,
        products=products,
        categories=categories,
    )


def seed_demo_market_data(db: Session) -> SeedDemoResponse:
    """Crea 6 usuarios sintéticos con inventario y eventos de consumo para T4.2."""
    from app.auth.service import hash_password as _hash

    existing_count = (
        db.query(func.count(User.id))
        .filter(User.email.like("%@secondserving.demo"))
        .scalar() or 0
    )
    if existing_count >= len(_DEMO_USERS):
        return SeedDemoResponse(
            status="already_seeded",
            users_created=0,
            items_created=0,
            events_created=0,
        )

    import random as _rng_mod
    rng = _rng_mod.Random(42)
    today = datetime.utcnow().date()
    demo_pw_hash = _hash("Demo@SecondServing2026")

    created_users = 0
    created_items = 0
    created_events = 0

    for user_data, purchase_list in zip(_DEMO_USERS, _USER_PURCHASES):
        user = db.query(User).filter(User.email == user_data["email"]).first()
        if not user:
            user = User(
                email=user_data["email"],
                full_name=user_data["full_name"],
                password_hash=demo_pw_hash,
                location=user_data.get("location"),
            )
            db.add(user)
            db.flush()
            created_users += 1

        for product_name, times in purchase_list:
            cat, unit, price_cop = _CATALOG[product_name]

            for t in range(times):
                # Spread purchases across the last 90 days; earlier purchases have higher t
                days_ago = rng.randint(10 + t * 8, 85 - t * 8)
                purchase_d: date = today - timedelta(days=days_ago)
                expiry_d: date = purchase_d + timedelta(days=rng.randint(7, 21))
                consumed_d: date = purchase_d + timedelta(
                    days=rng.randint(1, min(5, (expiry_d - purchase_d).days - 1))
                )

                item = InventoryItem(
                    user_id=user.id,
                    name=product_name,
                    category=cat,
                    quantity=Decimal("1"),
                    unit=unit,
                    unit_price=Decimal(str(price_cop)),
                    purchase_date=purchase_d,
                    expiry_date=expiry_d,
                    status="consumed",
                )
                db.add(item)
                db.flush()
                created_items += 1

                db.add(InventoryEvent(
                    user_id=user.id,
                    item_id=item.id,
                    event_type="registered",
                    quantity=Decimal("1"),
                    unit_price=Decimal(str(price_cop)),
                    occurred_at=datetime(purchase_d.year, purchase_d.month, purchase_d.day),
                ))
                db.add(InventoryEvent(
                    user_id=user.id,
                    item_id=item.id,
                    event_type="consumed",
                    quantity=Decimal("1"),
                    unit_price=Decimal(str(price_cop)),
                    occurred_at=datetime(consumed_d.year, consumed_d.month, consumed_d.day),
                ))
                created_events += 2

    db.commit()
    return SeedDemoResponse(
        status="seeded",
        users_created=created_users,
        items_created=created_items,
        events_created=created_events,
    )


# ── T1.1: Notification latency ────────────────────────────────────────────────

def get_notification_latency(db: Session, days: int = 30) -> dict:
    stats_sql = text("""
        WITH first_notification AS (
            SELECT (properties->>'item_id')::uuid AS item_id,
                   MIN(occurred_at)               AS first_notif_at
            FROM analytics_events
            WHERE event_name = 'notification_received'
              AND (properties->>'item_id') ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            GROUP BY properties->>'item_id'
        ),
        latencies AS (
            SELECT EXTRACT(EPOCH FROM (fn.first_notif_at - r.occurred_at)) AS seconds
            FROM inventory_events r
            JOIN first_notification fn ON fn.item_id = r.item_id
            WHERE r.event_type = 'registered'
              AND r.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
              AND fn.first_notif_at > r.occurred_at
        )
        SELECT
            COUNT(*)                                                            AS sample_size,
            COALESCE(AVG(seconds), 0)                                           AS avg_seconds,
            COALESCE(PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY seconds), 0) AS p50_seconds,
            COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY seconds), 0) AS p95_seconds,
            COALESCE(MAX(seconds), 0)                                           AS max_seconds
        FROM latencies;
    """)
    stats = db.execute(stats_sql, {"days": days}).mappings().one()

    histogram_sql = text("""
        WITH first_notification AS (
            SELECT (properties->>'item_id')::uuid AS item_id,
                   MIN(occurred_at)               AS first_notif_at
            FROM analytics_events
            WHERE event_name = 'notification_received'
              AND (properties->>'item_id') ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
            GROUP BY properties->>'item_id'
        ),
        latencies AS (
            SELECT EXTRACT(EPOCH FROM (fn.first_notif_at - r.occurred_at))/60.0 AS minutes
            FROM inventory_events r
            JOIN first_notification fn ON fn.item_id = r.item_id
            WHERE r.event_type = 'registered'
              AND r.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
              AND fn.first_notif_at > r.occurred_at
        ),
        buckets AS (
            SELECT
                CASE
                    WHEN minutes < 1   THEN '0-1 min'
                    WHEN minutes < 5   THEN '1-5 min'
                    WHEN minutes < 30  THEN '5-30 min'
                    WHEN minutes < 60  THEN '30-60 min'
                    ELSE                    '>60 min'
                END AS bucket,
                CASE
                    WHEN minutes < 1   THEN 1
                    WHEN minutes < 5   THEN 2
                    WHEN minutes < 30  THEN 3
                    WHEN minutes < 60  THEN 4
                    ELSE                    5
                END AS sort_order
            FROM latencies
        )
        SELECT bucket, sort_order, COUNT(*) AS count
        FROM buckets
        GROUP BY bucket, sort_order
        ORDER BY sort_order;
    """)
    rows = db.execute(histogram_sql, {"days": days}).mappings().all()

    return {
        "avg_seconds": float(stats["avg_seconds"]),
        "p50_seconds": float(stats["p50_seconds"]),
        "p95_seconds": float(stats["p95_seconds"]),
        "max_seconds": float(stats["max_seconds"]),
        "sample_size": int(stats["sample_size"]),
        "histogram": [{"bucket": r["bucket"], "count": int(r["count"])} for r in rows],
        "period_days": days,
    }


def get_inventory_events_summary(db: Session, days: int = 30) -> dict:
    sql = text("""
        SELECT
            COUNT(*) FILTER (WHERE r.event_type = 'registered') AS total_registered,
            COUNT(*) FILTER (
                WHERE r.event_type = 'registered'
                  AND (i.expiry_date - r.occurred_at::date) <= 3
            ) AS eligible_for_alert
        FROM inventory_events r
        LEFT JOIN inventory_items i ON i.id = r.item_id
        WHERE r.occurred_at > NOW() - (:days || ' days')::interval;
    """)
    row = db.execute(sql, {"days": days}).mappings().one()
    return {
        "total_registered": int(row["total_registered"] or 0),
        "eligible_for_alert": int(row["eligible_for_alert"] or 0),
        "period_days": days,
    }


# ── T2.3: Recipe interactions ─────────────────────────────────────────────────

def get_recipe_interactions_summary(db: Session, days: int = 30) -> dict:
    sql = text("""
        SELECT
            SUM(CASE WHEN action='cooked' THEN 1 ELSE 0 END) AS total_cooked,
            SUM(CASE WHEN action='viewed' THEN 1 ELSE 0 END) AS total_viewed,
            ROUND(
                100.0 * SUM(CASE WHEN action='cooked' THEN 1 ELSE 0 END)::numeric
                      / NULLIF(SUM(CASE WHEN action='viewed' THEN 1 ELSE 0 END), 0),
                1
            ) AS cook_through_rate,
            ROUND(AVG(CASE WHEN action='cooked' THEN inventory_matches END)::numeric, 1)
                AS avg_inventory_matches_on_cook
        FROM recipe_interactions
        WHERE occurred_at > NOW() - (:days || ' days')::interval;
    """)
    row = db.execute(sql, {"days": days}).mappings().one()
    return {
        "total_cooked": int(row["total_cooked"] or 0),
        "total_viewed": int(row["total_viewed"] or 0),
        "cook_through_rate": float(row["cook_through_rate"] or 0),
        "avg_inventory_matches_on_cook": (
            float(row["avg_inventory_matches_on_cook"])
            if row["avg_inventory_matches_on_cook"] is not None else None
        ),
        "period_days": days,
    }


def get_top_cooked_recipes(db: Session, days: int = 30, limit: int = 10) -> list[dict]:
    sql = text("""
        SELECT r.name, COUNT(*) AS cooks
        FROM recipe_interactions ri
        JOIN recipes r ON r.id = ri.recipe_id
        WHERE ri.action = 'cooked'
          AND ri.occurred_at > NOW() - (:days || ' days')::interval
        GROUP BY r.name
        ORDER BY cooks DESC
        LIMIT :limit;
    """)
    rows = db.execute(sql, {"days": days, "limit": limit}).mappings().all()
    return [{"name": r["name"], "cooks": int(r["cooks"])} for r in rows]


def get_views_vs_cooks(db: Session, days: int = 30, limit: int = 10) -> list[dict]:
    sql = text("""
        SELECT
            r.name,
            SUM(CASE WHEN ri.action='viewed' THEN 1 ELSE 0 END) AS views,
            SUM(CASE WHEN ri.action='cooked' THEN 1 ELSE 0 END) AS cooks,
            ROUND(
                100.0 * SUM(CASE WHEN ri.action='cooked' THEN 1 ELSE 0 END)::numeric
                      / NULLIF(SUM(CASE WHEN ri.action='viewed' THEN 1 ELSE 0 END), 0),
                1
            ) AS rate_pct
        FROM recipe_interactions ri
        JOIN recipes r ON r.id = ri.recipe_id
        WHERE ri.occurred_at > NOW() - (:days || ' days')::interval
        GROUP BY r.name
        ORDER BY cooks DESC, views DESC
        LIMIT :limit;
    """)
    rows = db.execute(sql, {"days": days, "limit": limit}).mappings().all()
    return [
        {
            "name": r["name"],
            "views": int(r["views"] or 0),
            "cooks": int(r["cooks"] or 0),
            "rate_pct": float(r["rate_pct"]) if r["rate_pct"] is not None else None,
        }
        for r in rows
    ]


# ── T3.4: Alert response times ────────────────────────────────────────────────

def _percentile_cont(sorted_values: list[float], p: float) -> float:
    """Linear-interpolated percentile equivalent to PostgreSQL PERCENTILE_CONT."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    k = (len(sorted_values) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    if lo == hi:
        return float(sorted_values[lo])
    return float(sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo))


def get_alert_response_times(
    db: Session, user_id: uuid.UUID, days: int = 30
) -> dict:
    """Tiempo (en horas) entre una notificación de alerta y la primera acción del usuario
    sobre el ítem referenciado (consumed/discarded). Solo cuenta deltas positivos.

    Si la muestra es menor a 5, devuelve ceros con histograma vacío
    (datos insuficientes — no se considera error).
    """
    deltas_sql = text("""
        SELECT
            EXTRACT(EPOCH FROM (next_action.first_action_at - notif.occurred_at)) / 3600.0
                AS hours
        FROM analytics_events notif
        CROSS JOIN LATERAL (
            SELECT MIN(occurred_at) AS first_action_at
            FROM inventory_events
            WHERE user_id = :user_id
              AND item_id = (notif.properties->>'item_id')::uuid
              AND event_type IN ('consumed', 'discarded')
              AND occurred_at > notif.occurred_at
        ) next_action
        WHERE notif.user_id = :user_id
          AND notif.event_name IN ('notification_received', 'notification_opened')
          AND notif.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
          AND notif.properties::jsonb ? 'item_id'
          AND (notif.properties->>'item_id')
              ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND next_action.first_action_at IS NOT NULL
          AND next_action.first_action_at > notif.occurred_at;
    """)

    rows = db.execute(deltas_sql, {"user_id": str(user_id), "days": days}).all()
    deltas = sorted(float(r[0]) for r in rows if r[0] is not None and float(r[0]) > 0)
    sample_size = len(deltas)

    if sample_size < 5:
        return {
            "avg_hours": 0.0,
            "p50_hours": 0.0,
            "p95_hours": 0.0,
            "max_hours": 0.0,
            "sample_size": sample_size,
            "period_days": days,
            "histogram": [],
        }

    avg_hours = sum(deltas) / sample_size
    p50_hours = _percentile_cont(deltas, 0.50)
    p95_hours = _percentile_cont(deltas, 0.95)
    max_hours = deltas[-1]

    buckets = [
        ("< 1h",   lambda d: d < 1),
        ("1\u20136h",  lambda d: 1 <= d < 6),
        ("6\u201324h", lambda d: 6 <= d < 24),
        ("> 24h",  lambda d: d >= 24),
    ]
    histogram = [
        {"bucket": label, "count": sum(1 for d in deltas if pred(d))}
        for label, pred in buckets
    ]

    return {
        "avg_hours": round(avg_hours, 2),
        "p50_hours": round(p50_hours, 2),
        "p95_hours": round(p95_hours, 2),
        "max_hours": round(max_hours, 2),
        "sample_size": sample_size,
        "period_days": days,
        "histogram": histogram,
    }


# ── T3.2: Waste reduction by recipe category ────────────────────────────────

def get_waste_reduction_by_recipe_category(
    db: Session, days: int = 30, rescue_window_days: int = 3
) -> WasteReductionByRecipeCategoryResponse:
    """T3.2 — Impacto de las recomendaciones de recetas en la reducción de desperdicio,
    agrupado por categoría de receta.

    Un ítem cuenta como "rescatado" si fue consumido por una receta (inventory_event
    con recipe_id no nulo) y la fecha de consumo estuvo a ≤ `rescue_window_days`
    de la fecha de expiración del ítem.
    """
    sql = text("""
        WITH cooks_in_window AS (
            SELECT
                r.category                              AS recipe_category,
                COUNT(*)                                AS cooks,
                COUNT(DISTINCT ri.user_id)              AS unique_users
            FROM recipe_interactions ri
            JOIN recipes r ON r.id = ri.recipe_id
            WHERE ri.action = 'cooked'
              AND ri.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
            GROUP BY r.category
        ),
        consumed_via_recipe AS (
            SELECT
                r.category                              AS recipe_category,
                COUNT(ie.id)                            AS items_consumed_total,
                COUNT(ie.id) FILTER (
                    WHERE (i.expiry_date - ie.occurred_at::date)
                          BETWEEN 0 AND CAST(:rescue_window AS INTEGER)
                )                                       AS items_rescued,
                COALESCE(SUM(
                    CASE WHEN (i.expiry_date - ie.occurred_at::date)
                              BETWEEN 0 AND CAST(:rescue_window AS INTEGER)
                         THEN ie.quantity * ie.unit_price ELSE 0 END
                ), 0)                                   AS value_rescued_cop
            FROM inventory_events ie
            JOIN inventory_items i ON i.id = ie.item_id
            JOIN recipes r ON r.id = ie.recipe_id
            WHERE ie.event_type = 'consumed'
              AND ie.recipe_id IS NOT NULL
              AND ie.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
            GROUP BY r.category
        )
        SELECT
            COALESCE(c.recipe_category, cv.recipe_category) AS recipe_category,
            COALESCE(c.cooks, 0)                            AS cooks,
            COALESCE(c.unique_users, 0)                     AS unique_users,
            COALESCE(cv.items_rescued, 0)                   AS items_rescued,
            COALESCE(cv.items_consumed_total, 0)            AS items_consumed_total,
            COALESCE(cv.value_rescued_cop, 0)               AS value_rescued_cop
        FROM cooks_in_window c
        FULL OUTER JOIN consumed_via_recipe cv
          ON c.recipe_category IS NOT DISTINCT FROM cv.recipe_category
        ORDER BY items_rescued DESC, cooks DESC;
    """)
    rows = db.execute(sql, {"days": days, "rescue_window": rescue_window_days}).mappings().all()

    items: list[WasteReductionByRecipeCategoryItem] = []
    total_cooks = 0
    total_rescued = 0
    total_value = Decimal("0")

    for row in rows:
        consumed_total = int(row["items_consumed_total"] or 0)
        rescued = int(row["items_rescued"] or 0)
        cooks = int(row["cooks"] or 0)
        value = Decimal(str(row["value_rescued_cop"] or 0))

        rescue_rate = round(rescued / consumed_total, 4) if consumed_total > 0 else 0.0

        items.append(WasteReductionByRecipeCategoryItem(
            recipe_category=row["recipe_category"],
            cooks=cooks,
            items_rescued=rescued,
            items_consumed_total=consumed_total,
            value_rescued_cop=value,
            rescue_rate=rescue_rate,
            unique_users=int(row["unique_users"] or 0),
        ))
        total_cooks += cooks
        total_rescued += rescued
        total_value += value

    return WasteReductionByRecipeCategoryResponse(
        period_days=days,
        rescue_window_days=rescue_window_days,
        total_cooks=total_cooks,
        total_items_rescued=total_rescued,
        total_value_rescued_cop=total_value,
        by_category=items,
    )


# ── T3.6: Favorites distribution ─────────────────────────────────────────────

def get_favorites_distribution(
    db: Session, top_ingredients: int = 10
) -> FavoritesDistributionResponse:
    """T3.6 — Cómo se distribuyen las categorías y los ingredientes principales
    de las recetas que los usuarios marcan como favoritas (cross-user, agregado).
    """
    total_favorites = db.query(func.count(RecipeFavorite.id)).scalar() or 0
    unique_users = (
        db.query(func.count(func.distinct(RecipeFavorite.user_id))).scalar() or 0
    )

    if total_favorites == 0:
        return FavoritesDistributionResponse(
            total_favorites=0,
            unique_users=0,
            by_category=[],
            top_ingredients=[],
        )

    cat_rows = (
        db.query(
            Recipe.category.label("category"),
            func.count(RecipeFavorite.id).label("favorites_count"),
            func.count(func.distinct(RecipeFavorite.user_id)).label("unique_users"),
        )
        .join(Recipe, Recipe.id == RecipeFavorite.recipe_id)
        .group_by(Recipe.category)
        .order_by(func.count(RecipeFavorite.id).desc())
        .all()
    )

    by_category = [
        FavoriteCategoryItem(
            category=row.category,
            favorites_count=row.favorites_count,
            unique_users=row.unique_users,
            pct_of_total=round(row.favorites_count / total_favorites, 4),
        )
        for row in cat_rows
    ]

    # Top ingredientes: contar cuántos favoritos contienen cada ingrediente.
    ing_rows = (
        db.query(
            func.lower(RecipeIngredient.ingredient_name).label("ingredient_name"),
            func.count(RecipeFavorite.id).label("favorites_count"),
        )
        .join(RecipeFavorite, RecipeFavorite.recipe_id == RecipeIngredient.recipe_id)
        .group_by(func.lower(RecipeIngredient.ingredient_name))
        .order_by(func.count(RecipeFavorite.id).desc())
        .limit(top_ingredients)
        .all()
    )

    top_ing = [
        FavoriteIngredientItem(
            ingredient_name=row.ingredient_name,
            favorites_count=row.favorites_count,
            pct_of_total=round(row.favorites_count / total_favorites, 4),
        )
        for row in ing_rows
    ]

    return FavoritesDistributionResponse(
        total_favorites=total_favorites,
        unique_users=unique_users,
        by_category=by_category,
        top_ingredients=top_ing,
    )


# ── T4.1: Segments behavioral patterns ───────────────────────────────────────

def _classify_segment(open_rate: float, recipes_cooked: int) -> str:
    if open_rate >= 0.6 and recipes_cooked >= 3:
        return "proactive"
    if open_rate < 0.2 and recipes_cooked == 0:
        return "passive"
    return "neutral"


def get_segments_patterns(db: Session, days: int = 30) -> SegmentsPatternsResponse:
    """T4.1 — Patrones de comportamiento que distinguen usuarios Passive vs Proactive.

    Clasifica a todos los usuarios con actividad reciente en uno de 3 segmentos
    y reporta, por segmento, métricas comparativas (recetas cocinadas, open rate
    de notificaciones, registros de inventario, ítems desperdiciados, tiempo de
    respuesta a alertas, favoritos, features más usadas).
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Universo: usuarios con CUALQUIER actividad en la ventana.
    activity_user_ids = set()
    for q in [
        db.query(func.distinct(RecipeInteraction.user_id))
            .filter(RecipeInteraction.occurred_at >= since),
        db.query(func.distinct(AnalyticsEvent.user_id))
            .filter(AnalyticsEvent.occurred_at >= since),
        db.query(func.distinct(InventoryEvent.user_id))
            .filter(InventoryEvent.occurred_at >= since),
    ]:
        for (uid,) in q.all():
            if uid is not None:
                activity_user_ids.add(uid)

    if not activity_user_ids:
        return SegmentsPatternsResponse(
            period_days=days,
            total_users_analyzed=0,
            segments=[],
        )

    # Pre-cómputo por usuario.
    cooked_rows = dict(
        db.query(RecipeInteraction.user_id, func.count(RecipeInteraction.id))
        .filter(
            RecipeInteraction.user_id.in_(activity_user_ids),
            RecipeInteraction.action == "cooked",
            RecipeInteraction.occurred_at >= since,
        )
        .group_by(RecipeInteraction.user_id)
        .all()
    )
    notif_recv = dict(
        db.query(AnalyticsEvent.user_id, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.user_id.in_(activity_user_ids),
            AnalyticsEvent.event_name == "notification_received",
            AnalyticsEvent.occurred_at >= since,
        )
        .group_by(AnalyticsEvent.user_id)
        .all()
    )
    notif_open = dict(
        db.query(AnalyticsEvent.user_id, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.user_id.in_(activity_user_ids),
            AnalyticsEvent.event_name == "notification_opened",
            AnalyticsEvent.occurred_at >= since,
        )
        .group_by(AnalyticsEvent.user_id)
        .all()
    )
    items_registered = dict(
        db.query(InventoryEvent.user_id, func.count(InventoryEvent.id))
        .filter(
            InventoryEvent.user_id.in_(activity_user_ids),
            InventoryEvent.event_type == "registered",
            InventoryEvent.occurred_at >= since,
        )
        .group_by(InventoryEvent.user_id)
        .all()
    )
    items_wasted = dict(
        db.query(InventoryEvent.user_id, func.count(InventoryEvent.id))
        .filter(
            InventoryEvent.user_id.in_(activity_user_ids),
            InventoryEvent.event_type == "discarded",
            InventoryEvent.occurred_at >= since,
        )
        .group_by(InventoryEvent.user_id)
        .all()
    )
    favorites_count = dict(
        db.query(RecipeFavorite.user_id, func.count(RecipeFavorite.id))
        .filter(RecipeFavorite.user_id.in_(activity_user_ids))
        .group_by(RecipeFavorite.user_id)
        .all()
    )

    # Features por usuario (mapa: user_id -> {feature: count}).
    feature_rows = (
        db.query(
            FeatureUsageEvent.user_id,
            FeatureUsageEvent.feature,
            func.count(FeatureUsageEvent.id).label("cnt"),
        )
        .filter(
            FeatureUsageEvent.user_id.in_(activity_user_ids),
            FeatureUsageEvent.timestamp >= since,
        )
        .group_by(FeatureUsageEvent.user_id, FeatureUsageEvent.feature)
        .all()
    )
    features_by_user: dict = defaultdict(dict)
    for uid, feat, cnt in feature_rows:
        features_by_user[uid][feat] = cnt

    # Alert response times por usuario.
    alert_response_avg = {}
    deltas_sql = text("""
        SELECT
            notif.user_id,
            EXTRACT(EPOCH FROM (next_action.first_action_at - notif.occurred_at)) / 3600.0
                AS hours
        FROM analytics_events notif
        CROSS JOIN LATERAL (
            SELECT MIN(occurred_at) AS first_action_at
            FROM inventory_events
            WHERE user_id = notif.user_id
              AND item_id = (notif.properties->>'item_id')::uuid
              AND event_type IN ('consumed', 'discarded')
              AND occurred_at > notif.occurred_at
        ) next_action
        WHERE notif.event_name IN ('notification_received', 'notification_opened')
          AND notif.occurred_at > NOW() - (CAST(:days AS INTEGER) * INTERVAL '1 day')
          AND notif.properties::jsonb ? 'item_id'
          AND (notif.properties->>'item_id')
              ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND next_action.first_action_at > notif.occurred_at;
    """)
    delta_rows = db.execute(deltas_sql, {"days": days}).all()
    per_user_deltas: dict = defaultdict(list)
    for uid, h in delta_rows:
        if h is not None and float(h) > 0:
            per_user_deltas[uid].append(float(h))
    for uid, vals in per_user_deltas.items():
        alert_response_avg[uid] = sum(vals) / len(vals)

    # Agrupar usuarios por segmento.
    buckets: dict[str, list] = {"passive": [], "neutral": [], "proactive": []}
    for uid in activity_user_ids:
        cooked = int(cooked_rows.get(uid, 0))
        recv = int(notif_recv.get(uid, 0))
        opened = int(notif_open.get(uid, 0))
        open_rate = (opened / recv) if recv > 0 else 0.0
        segment = _classify_segment(open_rate, cooked)
        buckets[segment].append({
            "user_id": uid,
            "cooked": cooked,
            "open_rate": open_rate,
            "registered": int(items_registered.get(uid, 0)),
            "wasted": int(items_wasted.get(uid, 0)),
            "favorites": int(favorites_count.get(uid, 0)),
            "alert_h": alert_response_avg.get(uid),
        })

    segments_out: list[SegmentPatternItem] = []
    for seg in ("passive", "neutral", "proactive"):
        users = buckets[seg]
        n = len(users)
        if n == 0:
            segments_out.append(SegmentPatternItem(
                segment=seg,
                user_count=0,
                avg_recipes_cooked_30d=0.0,
                avg_notification_open_rate=0.0,
                avg_items_registered_30d=0.0,
                avg_items_wasted_30d=0.0,
                avg_alert_response_hours=None,
                avg_favorites=0.0,
                top_features=[],
            ))
            continue

        cooked_avg = sum(u["cooked"] for u in users) / n
        or_avg = sum(u["open_rate"] for u in users) / n
        reg_avg = sum(u["registered"] for u in users) / n
        wasted_avg = sum(u["wasted"] for u in users) / n
        fav_avg = sum(u["favorites"] for u in users) / n

        alert_vals = [u["alert_h"] for u in users if u["alert_h"] is not None]
        alert_avg = (sum(alert_vals) / len(alert_vals)) if alert_vals else None

        # Top features dentro del segmento.
        feat_totals: dict = defaultdict(int)
        for u in users:
            for feat, cnt in features_by_user.get(u["user_id"], {}).items():
                feat_totals[feat] += cnt
        top_feats = [f for f, _ in sorted(feat_totals.items(), key=lambda x: x[1], reverse=True)[:3]]

        segments_out.append(SegmentPatternItem(
            segment=seg,
            user_count=n,
            avg_recipes_cooked_30d=round(cooked_avg, 2),
            avg_notification_open_rate=round(or_avg, 4),
            avg_items_registered_30d=round(reg_avg, 2),
            avg_items_wasted_30d=round(wasted_avg, 2),
            avg_alert_response_hours=round(alert_avg, 2) if alert_avg is not None else None,
            avg_favorites=round(fav_avg, 2),
            top_features=top_feats,
        ))

    return SegmentsPatternsResponse(
        period_days=days,
        total_users_analyzed=len(activity_user_ids),
        segments=segments_out,
    )


def get_match_distribution(db: Session, days: int = 30) -> list[dict]:
    sql = text("""
        WITH labeled AS (
            SELECT
                CASE
                    WHEN inventory_matches = 1 THEN '1'
                    WHEN inventory_matches = 2 THEN '2'
                    WHEN inventory_matches = 3 THEN '3'
                    WHEN inventory_matches = 4 THEN '4'
                    WHEN inventory_matches >= 5 THEN '5+'
                END AS matches,
                CASE
                    WHEN inventory_matches = 1 THEN 1
                    WHEN inventory_matches = 2 THEN 2
                    WHEN inventory_matches = 3 THEN 3
                    WHEN inventory_matches = 4 THEN 4
                    WHEN inventory_matches >= 5 THEN 5
                END AS sort_order
            FROM recipe_interactions
            WHERE action = 'cooked'
              AND inventory_matches IS NOT NULL
              AND occurred_at > NOW() - (:days || ' days')::interval
        )
        SELECT matches, sort_order, COUNT(*) AS count
        FROM labeled
        GROUP BY matches, sort_order
        ORDER BY sort_order;
    """)
    rows = db.execute(sql, {"days": days}).mappings().all()
    return [{"matches": r["matches"], "count": int(r["count"])} for r in rows]
