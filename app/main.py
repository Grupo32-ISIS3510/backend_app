from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.auth.router import router as auth_router
from app.inventory.router import router as inventory_router
from app.notifications.router import router as notifications_router
from app.recipes.router import router as recipes_router
from app.analytics.router import router as analytics_router
from app.sync.router import router as sync_router
from app.telemetry.router import router as telemetry_router
from app.shopping_list.router import router as shopping_list_router
from app.common.exceptions import AppException
from app.common.error_handlers import (
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ───────────────────────────────────────────────────────
# Orden: de más específico a más genérico (Starlette recorre el MRO de la excepción).
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(notifications_router)
app.include_router(recipes_router)
app.include_router(analytics_router)
app.include_router(sync_router)
app.include_router(telemetry_router)
app.include_router(shopping_list_router)


# ── Scheduler (notificaciones de vencimiento) ────────────────────────────────

def scheduled_expiry_check():
    """Función que APScheduler ejecuta cada hora."""
    db = SessionLocal()
    try:
        from app.notifications.service import send_expiry_alerts
        send_expiry_alerts(db)
    finally:
        db.close()


# Iniciar el scheduler cuando arranca el servidor
scheduler = BackgroundScheduler()
scheduler.add_job(
    scheduled_expiry_check,
    "interval",
    hours=max(1, settings.notifications_scheduler_hours),
)
scheduler.start()


@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()


# ── Rutas base ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.app_env,
        "app": settings.app_name,
    }
