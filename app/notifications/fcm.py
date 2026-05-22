from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from app.config import get_settings
from pathlib import Path

settings = get_settings()

firebase_available = False
firebase_error: Optional[str] = None


def initialize_firebase_once() -> bool:
    global firebase_available, firebase_error

    if firebase_available:
        return True

    credentials_path = (settings.firebase_credentials_path or "").strip()
    if not credentials_path:
        firebase_error = "FIREBASE_CREDENTIALS_PATH no está configurado en .env"
        return False

    credentials_file = Path(credentials_path)
    if not credentials_file.is_file():
        firebase_error = f"FIREBASE_CREDENTIALS_PATH inválido: no existe el archivo {credentials_path}"
        return False

    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(credentials_file))
            firebase_admin.initialize_app(cred)
        firebase_available = True
        firebase_error = None
        return True
    except Exception as error:
        firebase_error = f"No se pudo inicializar Firebase Admin: {error}"
        return False


def send_expiry_notification(fcm_token: str, product_name: str, days_remaining: int) -> bool:
    """
    Envía una notificación push de vencimiento próximo.
    Retorna True si se envió correctamente, False si falló.
    """
    if not initialize_firebase_once():
        print(f"[FCM] Firebase no disponible: {firebase_error}")
        print(f"[FCM] Simulando notificación para token {fcm_token[:20]}...")
        return False

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title="🕐 Producto por vencer",
                body=f"{product_name} vence en {days_remaining} día{'s' if days_remaining != 1 else ''}. ¡Úsalo antes de que se dañe!"
            ),
            data={
                "product_name": product_name,
                "days_remaining": str(days_remaining),
                "type": "expiry_alert"
            },
            token=fcm_token
        )
        messaging.send(message)
        return True
    except Exception as e:
        print(f"[FCM] Error enviando notificación: {e}")
        return False


def send_bulk_expiry_notifications(tokens: list[str], product_name: str, days_remaining: int):
    """Envía la misma notificación a múltiples dispositivos (hogar compartido)."""
    if not initialize_firebase_once() or not tokens:
        return

    message = messaging.MulticastMessage(
        notification=messaging.Notification(
            title="🕐 Producto por vencer",
            body=f"{product_name} vence en {days_remaining} día{'s' if days_remaining != 1 else ''}."
        ),
        data={
            "product_name": product_name,
            "days_remaining": str(days_remaining),
            "type": "expiry_alert"
        },
        tokens=tokens
    )
    try:
        response = messaging.send_each_for_multicast(message)
        print(f"[FCM] {response.success_count} enviadas, {response.failure_count} fallidas")
    except Exception as e:
        print(f"[FCM] Error en envío masivo: {e}")


def send_multicast_notification(
    tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str],
) -> dict:
    if not tokens:
        return {"success_count": 0, "failure_count": 0, "results": []}

    if not initialize_firebase_once():
        raise RuntimeError(firebase_error or "Firebase no disponible")

    try:
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={key: str(value) for key, value in data.items()},
            tokens=tokens,
        )
        batch_response = messaging.send_each_for_multicast(message)

        results = []
        for token, token_response in zip(tokens, batch_response.responses):
            if token_response.success:
                results.append(
                    {
                        "token": token,
                        "success": True,
                        "message_id": token_response.message_id,
                        "error_code": None,
                        "error_message": None,
                    }
                )
            else:
                exception = token_response.exception
                results.append(
                    {
                        "token": token,
                        "success": False,
                        "message_id": None,
                        "error_code": getattr(exception, "code", None),
                        "error_message": str(exception),
                    }
                )

        return {
            "success_count": batch_response.success_count,
            "failure_count": batch_response.failure_count,
            "results": results,
        }
    except Exception as error:
        raise RuntimeError(f"Error enviando push con Firebase: {error}") from error
