from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.common.exceptions import AppException


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.status_code,
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": exc.timestamp,
        },
        headers=getattr(exc, "headers", None) or {},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.status_code,
            "code": "HTTP_ERROR",
            "message": exc.detail if isinstance(exc.detail, str) else "Error en la solicitud.",
            "details": None,
            "timestamp": _utc_now(),
        },
        headers=getattr(exc, "headers", None) or {},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = [
        {
            "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
            # Pydantic v2 prefixes custom messages with "Value error, " — strip it
            "message": err["msg"].replace("Value error, ", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "status": 422,
            "code": "VALIDATION_ERROR",
            "message": "Los datos enviados contienen errores de validación.",
            "details": field_errors,
            "timestamp": _utc_now(),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # 500: nunca exponer stack traces ni detalles de infraestructura
    return JSONResponse(
        status_code=500,
        content={
            "status": 500,
            "code": "INTERNAL_ERROR",
            "message": "Ocurrió un error inesperado. Por favor intenta de nuevo más tarde.",
            "details": None,
            "timestamp": _utc_now(),
        },
    )
