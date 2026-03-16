from datetime import datetime, timezone

from fastapi import HTTPException


class AppException(HTTPException):
    """Excepción estándar de la app. Genera respuestas de error con estructura unificada."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details=None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details
        self.timestamp = datetime.now(timezone.utc).isoformat()


class ErrorCode:
    # ── Autenticación ──────────────────────────────────────
    UNAUTHORIZED = "UNAUTHORIZED"
    TOKEN_INVALID = "TOKEN_INVALID"

    # ── Validación ─────────────────────────────────────────
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # ── Genéricos ──────────────────────────────────────────
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"

    # ── Inventario ─────────────────────────────────────────
    ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
    ITEM_NOT_ACTIVE = "ITEM_NOT_ACTIVE"
    QUANTITY_EXCEEDS_STOCK = "QUANTITY_EXCEEDS_STOCK"

    # ── Usuarios ───────────────────────────────────────────
    EMAIL_ALREADY_REGISTERED = "EMAIL_ALREADY_REGISTERED"
