from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime
import uuid

from app.notifications.models import DeviceToken, NotificationPreference
from app.notifications.schemas import DeviceTokenRegister, NotificationPreferenceUpdate
from app.notifications.fcm import send_expiry_notification
from app.inventory.models import InventoryItem


def register_device_token(db: Session, user_id: uuid.UUID, data: DeviceTokenRegister):
    # Si ya existe un token para esta plataforma, lo actualiza en vez de duplicar
    existing = db.query(DeviceToken).filter(
        and_(
            DeviceToken.user_id == user_id,
            DeviceToken.platform == data.platform
        )
    ).first()

    if existing:
        existing.fcm_token = data.fcm_token
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing

    token = DeviceToken(
        user_id=user_id,
        fcm_token=data.fcm_token,
        platform=data.platform
    )
    db.add(token)
    db.commit()
    return token


def get_or_create_preferences(db: Session, user_id: uuid.UUID) -> NotificationPreference:
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()

    if not prefs:
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def update_preferences(db: Session, user_id: uuid.UUID, data: NotificationPreferenceUpdate):
    prefs = get_or_create_preferences(db, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    db.commit()
    db.refresh(prefs)
    return prefs


def send_expiry_alerts(db: Session):
    """
    Tarea periódica — revisa todos los usuarios y envía alertas
    para productos que vencen dentro del umbral configurado.
    Esta función será llamada por APScheduler cada hora.
    """
    # Obtener todos los usuarios con notificaciones activas
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.push_enabled == True
    ).all()

    current_hour = datetime.utcnow().hour

    for pref in preferences:
        # Respetar horario de no molestar
        if pref.quiet_hours_start is not None and pref.quiet_hours_end is not None:
            in_quiet_hours = (
                pref.quiet_hours_start <= current_hour or
                current_hour < pref.quiet_hours_end
            )
            if in_quiet_hours:
                continue

        # Buscar productos por vencer para este usuario
        from datetime import date, timedelta
        expiry_threshold = date.today() + timedelta(days=pref.days_before_expiry)

        expiring_items = db.query(InventoryItem).filter(
            and_(
                InventoryItem.user_id == pref.user_id,
                InventoryItem.status == "active",
                InventoryItem.expiry_date <= expiry_threshold
            )
        ).all()

        if not expiring_items:
            continue

        # Obtener tokens activos del usuario
        tokens = db.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id == pref.user_id,
                DeviceToken.is_active == True
            )
        ).all()

        if not tokens:
            continue

        # Enviar una notificación por cada producto próximo a vencer
        for item in expiring_items:
            for device in tokens:
                send_expiry_notification(
                    fcm_token=device.fcm_token,
                    product_name=item.name,
                    days_remaining=item.days_remaining
                )