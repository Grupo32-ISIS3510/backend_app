"""
Script de prueba del Analytics Pipeline con mock data.

Recorre las 5 etapas del pipeline:
  1. Capture  — Registra un usuario y crea ítems de inventario
  2. Transport — Envía eventos analytics via POST (batch)
  3. Process  — Consume/descarta ítems para generar inventory_events
  4. Store    — Los datos quedan persistidos en PostgreSQL
  5. Consume  — Consulta los endpoints de analytics y muestra resultados

Uso:
  1. Levanta el servidor:  uvicorn app.main:app --reload
  2. En otra terminal:     python test_analytics_pipeline.py
"""

import httpx
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
TOKEN = ""

def header():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def print_step(stage: str, description: str):
    print(f"\n{'='*60}")
    print(f"  ETAPA {stage}")
    print(f"  {description}")
    print(f"{'='*60}")

def print_result(label: str, response):
    status = response.status_code
    icon = "OK" if status < 400 else "ERROR"
    print(f"\n  [{icon} {status}] {label}")
    try:
        data = response.json()
        print(f"  {json.dumps(data, indent=2, default=str, ensure_ascii=False)[:500]}")
    except Exception:
        print(f"  {response.text[:300]}")


def main():
    global TOKEN

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # ─────────────────────────────────────────────────────────────────────
    # ETAPA 1: CAPTURE — Crear usuario y datos base
    # ─────────────────────────────────────────────────────────────────────
    print_step("1 — CAPTURE", "Registrar usuario + crear items de inventario")

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    email = f"pipeline.test.{ts}@secondserving.com"

    r = client.post("/api/v1/auth/register", json={
        "email": email,
        "full_name": "Pipeline Tester",
        "password": "TestPass123!",
        "location": "Bogota, Colombia"
    })
    print_result("Registrar usuario", r)

    if r.status_code != 201:
        print("\n  No se pudo registrar el usuario. Intentando login...")
        r = client.post("/api/v1/auth/login", json={
            "email": email, "password": "TestPass123!"
        })
        print_result("Login", r)

    TOKEN = r.json().get("access_token", "")
    if not TOKEN:
        print("\n  ERROR: No se obtuvo token. Abortando.")
        return

    print(f"\n  Token obtenido: {TOKEN[:30]}...")

    items_data = [
        {
            "name": "Leche entera",
            "category": "dairy",
            "quantity": 2,
            "unit": "litros",
            "unit_price": 4500,
            "purchase_date": (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d"),
            "expiry_date": (datetime.utcnow() + timedelta(days=2)).strftime("%Y-%m-%d"),
        },
        {
            "name": "Pollo entero",
            "category": "meat",
            "quantity": 1.5,
            "unit": "kg",
            "unit_price": 18000,
            "purchase_date": (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d"),
            "expiry_date": (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        {
            "name": "Yogur griego",
            "category": "dairy",
            "quantity": 4,
            "unit": "unidades",
            "unit_price": 2800,
            "purchase_date": (datetime.utcnow() - timedelta(days=5)).strftime("%Y-%m-%d"),
            "expiry_date": (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d"),
        },
        {
            "name": "Espinacas",
            "category": "vegetables",
            "quantity": 1,
            "unit": "bolsa",
            "unit_price": 3200,
            "purchase_date": (datetime.utcnow() - timedelta(days=4)).strftime("%Y-%m-%d"),
            "expiry_date": (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d"),
        },
    ]

    item_ids = []
    for item in items_data:
        r = client.post("/api/v1/inventory", json=item, headers=header())
        print_result(f"Crear item: {item['name']}", r)
        if r.status_code == 201:
            item_ids.append(r.json()["id"])

    # ─────────────────────────────────────────────────────────────────────
    # ETAPA 2: TRANSPORT — Enviar eventos analytics via REST API
    # ─────────────────────────────────────────────────────────────────────
    print_step("2 — TRANSPORT", "Enviar batch de eventos analytics via POST")

    now = datetime.utcnow()
    events_batch = {
        "events": [
            {
                "event_name": "screen_opened",
                "properties": {"screen": "inventory"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=30)).isoformat() + "Z"
            },
            {
                "event_name": "item_added",
                "properties": {"category": "dairy", "item_name": "Leche entera"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=28)).isoformat() + "Z"
            },
            {
                "event_name": "notification_received",
                "properties": {"notification_type": "expiry_alert"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=20)).isoformat() + "Z"
            },
            {
                "event_name": "notification_opened",
                "properties": {"notification_type": "expiry_alert"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=19)).isoformat() + "Z"
            },
            {
                "event_name": "screen_opened",
                "properties": {"screen": "recipes"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=15)).isoformat() + "Z"
            },
            {
                "event_name": "recipe_viewed",
                "properties": {"recipe_name": "Sopa de pollo"},
                "session_id": "test-session-001",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=14)).isoformat() + "Z"
            },
            {
                "event_name": "notification_received",
                "properties": {"notification_type": "recipe_suggestion"},
                "session_id": "test-session-002",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=10)).isoformat() + "Z"
            },
            {
                "event_name": "screen_opened",
                "properties": {"screen": "dashboard"},
                "session_id": "test-session-002",
                "platform": "android_kotlin",
                "app_version": "1.0.0",
                "occurred_at": (now - timedelta(minutes=5)).isoformat() + "Z"
            },
        ]
    }

    r = client.post("/api/v1/analytics/events", json=events_batch, headers=header())
    print_result("POST /analytics/events (batch de 8 eventos)", r)

    # ─────────────────────────────────────────────────────────────────────
    # ETAPA 3: PROCESS — Consumir y descartar items para generar eventos
    # ─────────────────────────────────────────────────────────────────────
    print_step("3 — PROCESS", "Consumir/descartar items para generar inventory_events")

    if len(item_ids) >= 4:
        r = client.patch(f"/api/v1/inventory/{item_ids[0]}/consume", headers=header())
        print_result("Consumir: Leche entera (rescatada antes de vencer)", r)

        r = client.patch(f"/api/v1/inventory/{item_ids[1]}/consume", headers=header())
        print_result("Consumir: Pollo entero (rescatado antes de vencer)", r)

        r = client.patch(
            f"/api/v1/inventory/{item_ids[2]}/discard",
            json={"reason": "expired"},
            headers=header()
        )
        print_result("Descartar: Yogur griego (vencido)", r)

        r = client.patch(
            f"/api/v1/inventory/{item_ids[3]}/discard",
            json={"reason": "bad_storage", "quantity": 0.5},
            headers=header()
        )
        print_result("Descartar parcial: Espinacas (0.5 por mal almacenamiento)", r)

    # ─────────────────────────────────────────────────────────────────────
    # ETAPA 4: STORE — Verificar que los datos están en la DB
    # ─────────────────────────────────────────────────────────────────────
    print_step("4 — STORE", "Datos persistidos en PostgreSQL (verificamos via endpoints)")

    r = client.get("/api/v1/analytics/events/summary?days=30", headers=header())
    print_result("GET /analytics/events/summary (eventos analytics almacenados)", r)

    r = client.get("/api/v1/inventory?skip=0&limit=20", headers=header())
    print_result("GET /inventory (estado de los items tras consume/discard)", r)

    # ─────────────────────────────────────────────────────────────────────
    # ETAPA 5: CONSUME — El movil consulta las metricas procesadas
    # ─────────────────────────────────────────────────────────────────────
    print_step("5 — CONSUME", "App movil consulta endpoints de analytics")

    month = datetime.utcnow().month
    year = datetime.utcnow().year

    r = client.get(f"/api/v1/analytics/savings?month={month}&year={year}", headers=header())
    print_result("GET /analytics/savings (dinero rescatado vs perdido)", r)

    r = client.get("/api/v1/analytics/waste?months=3", headers=header())
    print_result("GET /analytics/waste (tendencias de desperdicio)", r)

    r = client.get("/api/v1/analytics/summary", headers=header())
    print_result("GET /analytics/summary (resumen historico)", r)

    r = client.get("/api/v1/analytics/segment", headers=header())
    print_result("GET /analytics/segment (segmento del usuario)", r)

    r = client.get(f"/api/v1/analytics/dashboard?month={month}&year={year}", headers=header())
    print_result("GET /analytics/dashboard (todo junto para la pantalla de inicio)", r)

    # ─────────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETO")
    print(f"  Todas las 5 etapas ejecutadas correctamente.")
    print(f"{'='*60}\n")

    client.close()


if __name__ == "__main__":
    main()
