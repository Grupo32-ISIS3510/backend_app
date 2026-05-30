"""
Seed para verificar la BQ T3.4 (Alert Response Time — distribución por categoría).

Crea un usuario, 8 ítems en 4 categorías, inserta directamente filas en
notification_dispatches con created_at escalonados (status='sent') para
cubrir todos los buckets del histograma, consume los ítems vía HTTP para
generar inventory_events en "ahora", y consulta el endpoint mostrando la
distribución resultante.

Uso (en otra terminal mientras corre uvicorn):
    uvicorn app.main:app --reload
    python seed_alert_response_demo.py
"""

import json
import uuid
from datetime import datetime, timedelta

import httpx

from app.database import SessionLocal
from app.notifications.models import NotificationDispatch


BASE_URL = "http://localhost:8000"

# Cada escenario fija el "lag" (minutos entre el envío de la alerta y el
# consumo) para caer en un bucket distinto, repartido entre categorías.
SCENARIOS = [
    {"name": "Leche entera",  "category": "dairy",      "lag_min": 3},     # < 5 min
    {"name": "Yogur griego",  "category": "dairy",      "lag_min": 12},    # 5-15 min
    {"name": "Pollo crudo",   "category": "meat",       "lag_min": 22},    # 15-30 min
    {"name": "Carne molida",  "category": "meat",       "lag_min": 45},    # 30-60 min
    {"name": "Espinacas",     "category": "vegetables", "lag_min": 95},    # 1-3 h
    {"name": "Lechuga",       "category": "vegetables", "lag_min": 240},   # 3-6 h
    {"name": "Manzanas",      "category": "fruits",     "lag_min": 720},   # 6-24 h
    {"name": "Fresas",        "category": "fruits",     "lag_min": 1800},  # > 24 h
]


def main() -> None:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    email = f"alert.demo.{ts}@secondserving.com"
    password = "TestPass123!"

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # 1. Registrar usuario nuevo (o login si ya existe)
    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Alert Demo",
        "password": password,
        "location": "Bogota, Colombia",
    })
    if r.status_code != 201:
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    payload = r.json()
    token = payload["access_token"]
    user_id = uuid.UUID(payload["user"]["id"])
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"[1] Usuario:  {email}  id={user_id}")

    # 2. Crear los items de inventario via HTTP
    today = datetime.utcnow().date()
    item_ids: list[uuid.UUID] = []
    for s in SCENARIOS:
        resp = client.post("/api/v1/inventory", headers=headers, json={
            "name": s["name"],
            "category": s["category"],
            "quantity": 1,
            "unit": "unit",
            "unit_price": 1000,
            "purchase_date": (today - timedelta(days=2)).isoformat(),
            "expiry_date": (today + timedelta(days=2)).isoformat(),
        })
        if resp.status_code != 201:
            raise RuntimeError(f"Fallo creando ítem {s['name']}: {resp.status_code} {resp.text}")
        item_ids.append(uuid.UUID(resp.json()["id"]))
    print(f"[2] Items:    {len(item_ids)} creados ({', '.join(s['category'] for s in SCENARIOS)})")

    # 3. Insertar notification_dispatches con created_at desplazado al pasado.
    #    Estos serían escritos normalmente por el scheduler/flujo item-registered,
    #    pero en local sin tokens FCM no llegarían a status='sent'.
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        for s, item_id in zip(SCENARIOS, item_ids):
            db.add(NotificationDispatch(
                user_id=user_id,
                item_id=item_id,
                notification_type="expiry_alert",
                dedupe_key=f"{item_id}:expiry_alert:demo:{ts}:{s['lag_min']}",
                source="qa",
                status="sent",
                sent_count=1,
                failed_count=0,
                invalid_tokens_count=0,
                created_at=now - timedelta(minutes=s["lag_min"]),
            ))
        db.commit()
    finally:
        db.close()
    print(f"[3] Despachos:{len(item_ids)} insertados (status='sent') con lag {[s['lag_min'] for s in SCENARIOS]} min")

    # 4. Consumir los items via HTTP -> inventory_events.occurred_at = "ahora"
    for item_id in item_ids:
        client.patch(f"/api/v1/inventory/{item_id}/consume", headers=headers)
    print(f"[4] Consumidos: {len(item_ids)} ítems")

    # 5. Consultar la BQ
    r = client.get("/api/v1/analytics/alert-response-times?days=30", headers=headers)
    print(f"\n[5] GET /alert-response-times  -> HTTP {r.status_code}")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    client.close()


if __name__ == "__main__":
    main()
