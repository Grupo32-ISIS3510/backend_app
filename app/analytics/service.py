from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import Date, cast, extract, func, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.inventory.models import InventoryEvent, InventoryItem
from app.recipes.models import RecipeInteraction
from app.analytics.models import AnalyticsEvent
from app.analytics.schemas import (
    AnalyticsEventBatch,
    AnalyticsEventResponse,
    CategoryTrendItem,
    DashboardResponse,
    EventCount,
    EventsSummaryResponse,
    MarketProductTrendsResponse,
    ProductTrendItem,
    SavingsResponse,
    SeedDemoResponse,
    UserSegmentResponse,
    WasteSummaryResponse,
    WasteTrendItem,
)


# ── T4.2 seed constants ───────────────────────────────────────────────────────

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

# list of (product_name, times_bought) per demo user (same order as _DEMO_USERS)
_USER_PURCHASES: list[list[tuple[str, int]]] = [
    # Ana García – compras familiares típicas
    [("Leche", 3), ("Arroz Blanco", 3), ("Huevos", 3), ("Tomate", 2),
     ("Banano", 2), ("Pan Tajado", 2), ("Queso Campesino", 2), ("Café Molido", 2),
     ("Aceite de Cocina", 1), ("Lechuga", 1)],
    # Carlos Rodríguez – dieta alta en proteínas
    [("Leche", 2), ("Arroz Blanco", 2), ("Pechuga de Pollo", 3), ("Zanahoria", 2),
     ("Papa", 3), ("Lenteja", 2), ("Avena", 1), ("Manzana", 2), ("Huevos", 2)],
    # María López – frutas y verduras
    [("Yogur Natural", 2), ("Leche", 2), ("Banano", 3), ("Naranja", 2),
     ("Tomate", 3), ("Cebolla", 2), ("Arroz Blanco", 2), ("Azúcar", 2), ("Manzana", 1)],
    # José Martínez – soltero, productos prácticos
    [("Huevos", 3), ("Atún en Lata", 2), ("Arroz Blanco", 3), ("Pan Tajado", 3),
     ("Café Molido", 3), ("Jugo de Naranja", 2), ("Agua Mineral", 2), ("Leche", 1)],
    # Laura Hernández – amante de los lácteos
    [("Leche", 3), ("Queso Campesino", 3), ("Mantequilla", 2), ("Arroz Blanco", 2),
     ("Papa", 2), ("Cebolla", 3), ("Tomate", 2), ("Manzana", 2), ("Yogur Natural", 1)],
    # Diego Vargas – dieta costeña
    [("Pechuga de Pollo", 2), ("Huevos", 2), ("Arroz Blanco", 3), ("Banano", 2),
     ("Naranja", 3), ("Agua Mineral", 3), ("Aceite de Cocina", 2), ("Azúcar", 2),
     ("Lenteja", 1)],
]


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
            SELECT (metadata->>'item_id')::uuid AS item_id,
                   MIN(occurred_at)             AS first_notif_at
            FROM analytics_events
            WHERE event_name = 'notification_received'
              AND metadata ? 'item_id'
            GROUP BY metadata->>'item_id'
        ),
        latencies AS (
            SELECT EXTRACT(EPOCH FROM (fn.first_notif_at - r.occurred_at)) AS seconds
            FROM inventory_events r
            JOIN first_notification fn ON fn.item_id = r.item_id
            WHERE r.event_type = 'registered'
              AND r.occurred_at > NOW() - (:days || ' days')::interval
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
            SELECT (metadata->>'item_id')::uuid AS item_id,
                   MIN(occurred_at)             AS first_notif_at
            FROM analytics_events
            WHERE event_name = 'notification_received'
              AND metadata ? 'item_id'
            GROUP BY metadata->>'item_id'
        ),
        latencies AS (
            SELECT EXTRACT(EPOCH FROM (fn.first_notif_at - r.occurred_at))/60.0 AS minutes
            FROM inventory_events r
            JOIN first_notification fn ON fn.item_id = r.item_id
            WHERE r.event_type = 'registered'
              AND r.occurred_at > NOW() - (:days || ' days')::interval
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
