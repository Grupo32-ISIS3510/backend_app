from typing import Any, Optional


def success_response(data: Any) -> dict:
    """Envuelve datos en el formato de respuesta estándar exitosa."""
    return {"status": "success", "data": data, "error": None}


def error_response(code: str, message: str) -> dict:
    """Formato estándar para respuestas de error (usar junto con HTTPException)."""
    return {"status": "error", "data": None, "error": {"code": code, "message": message}}
