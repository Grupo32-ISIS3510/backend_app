import firebase_admin
from firebase_admin import credentials, messaging
from app.config import get_settings

settings = get_settings()

# Inicializa Firebase una sola vez al arrancar el servidor.
# Si el archivo de credenciales está vacío (desarrollo sin Firebase),
# el bloque except evita que el servidor crashee.
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        firebase_admin.initialize_app(cred)
    firebase_available = True
except Exception as e:
    print(f"[FCM] Firebase no inicializado: {e}")
    firebase_available = False


def send_expiry_notification(fcm_token: str, product_name: str, days_remaining: int) -> bool:
    """
    Envía una notificación push de vencimiento próximo.
    Retorna True si se envió correctamente, False si falló.
    """
    if not firebase_available:
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
    if not firebase_available or not tokens:
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