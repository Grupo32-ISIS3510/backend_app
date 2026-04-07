from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timedelta
import uuid
import logging

from app.config import get_settings
from app.common.exceptions import AppException, ErrorCode
from app.notifications.models import DeviceToken, NotificationPreference, NotificationDispatch
from app.notifications.schemas import (
    DeviceTokenRegister,
    NotificationPreferenceUpdate,
    TestSendSelfRequest,
)
from app.notifications.fcm import send_multicast_notification
from app.inventory.models import InventoryItem

logger = logging.getLogger(__name__)
settings = get_settings()

NOTIFICATION_TYPE_EXPIRY_ALERT = "expiry_alert"


def _build_expiry_body(item_name: str, days_remaining: int) -> str:
    if days_remaining <= 0:
        return f"{item_name} vence hoy"
    return f"{item_name} vence en {days_remaining} días"


def _build_expiry_payload(item: InventoryItem) -> tuple[str, str, dict[str, str]]:
    title = "⚠️ Alimentos próximos a vencer"
    body = _build_expiry_body(item.name, item.days_remaining)
    data = {
        "route": "/home",
        "item_id": str(item.id),
        "item_name": item.name,
        "days_remaining": str(item.days_remaining),
        "type": NOTIFICATION_TYPE_EXPIRY_ALERT,
    }
    return title, body, data


def _is_in_quiet_hours(prefs: NotificationPreference, hour_utc: int) -> bool:
    if prefs.quiet_hours_start is None or prefs.quiet_hours_end is None:
        return False
    return prefs.quiet_hours_start <= hour_utc or hour_utc < prefs.quiet_hours_end


def _is_invalid_token(error_code: str | None, error_message: str | None) -> bool:
    code = (error_code or "").lower()
    message = (error_message or "").lower()
    return (
        "unregistered" in code
        or "registration-token-not-registered" in code
        or "invalid-argument" in code
        or "invalid registration token" in message
        or "not registered" in message
        or "senderid mismatch" in message
    )


def _build_dedupe_key(item_id: uuid.UUID, notification_type: str, target_date: date) -> str:
    return f"{item_id}:{notification_type}:{target_date.isoformat()}"


def _create_dispatch(
    db: Session,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    source: str,
) -> NotificationDispatch | None:
    dedupe_key = _build_dedupe_key(item_id, NOTIFICATION_TYPE_EXPIRY_ALERT, date.today())
    dispatch = NotificationDispatch(
        user_id=user_id,
        item_id=item_id,
        notification_type=NOTIFICATION_TYPE_EXPIRY_ALERT,
        dedupe_key=dedupe_key,
        source=source,
        status="processing",
    )
    db.add(dispatch)
    try:
        db.flush()
        return dispatch
    except IntegrityError:
        db.rollback()
        return None


def _mark_invalid_tokens_inactive(db: Session, devices: list[DeviceToken], invalid_tokens: set[str]) -> int:
    if not invalid_tokens:
        return 0

    invalid_count = 0
    now = datetime.utcnow()
    for device in devices:
        if device.fcm_token in invalid_tokens and device.is_active:
            device.is_active = False
            device.updated_at = now
            invalid_count += 1
    return invalid_count


def _send_payload_to_devices(
    db: Session,
    devices: list[DeviceToken],
    title: str,
    body: str,
    data: dict[str, str],
    source: str,
    user_id: uuid.UUID,
    item_id: uuid.UUID | None,
) -> dict:
    if not devices:
        return {
            "status": "no_devices",
            "sent_count": 0,
            "failed_count": 0,
            "invalid_tokens_count": 0,
            "reason": "no_active_device_tokens",
        }

    token_map = {device.fcm_token: device for device in devices}
    fcm_tokens = list(token_map.keys())
    try:
        send_result = send_multicast_notification(fcm_tokens, title, body, data)
    except Exception as error:
        logger.error(
            "notification_dispatch_error source=%s user_id=%s item_id=%s reason=%s",
            source,
            user_id,
            item_id,
            str(error),
        )
        return {
            "status": "failed",
            "sent_count": 0,
            "failed_count": len(fcm_tokens),
            "invalid_tokens_count": 0,
            "reason": str(error),
        }

    invalid_tokens: set[str] = set()
    failure_reasons: list[str] = []
    for result in send_result["results"]:
        if result["success"]:
            continue
        if result["error_message"]:
            failure_reasons.append(str(result["error_message"]))
        if _is_invalid_token(result["error_code"], result["error_message"]):
            invalid_tokens.add(result["token"])

    invalid_tokens_count = _mark_invalid_tokens_inactive(db, devices, invalid_tokens)

    logger.info(
        "notification_dispatch source=%s user_id=%s item_id=%s sent=%s failed=%s invalid_tokens=%s",
        source,
        user_id,
        item_id,
        send_result["success_count"],
        send_result["failure_count"],
        invalid_tokens_count,
    )

    return {
        "status": "sent" if send_result["success_count"] > 0 else "failed",
        "sent_count": send_result["success_count"],
        "failed_count": send_result["failure_count"],
        "invalid_tokens_count": invalid_tokens_count,
        "reason": "; ".join(failure_reasons[:3]) if failure_reasons else None,
    }


def register_device_token(db: Session, user_id: uuid.UUID, data: DeviceTokenRegister):
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


def process_item_expiry_notification(
    db: Session,
    user_id: uuid.UUID,
    item: InventoryItem,
    source: str,
) -> dict:
    prefs = get_or_create_preferences(db, user_id)
    if not prefs.push_enabled:
        return {"status": "skipped", "reason": "push_disabled"}

    if item.status != "active":
        return {"status": "skipped", "reason": "item_not_active"}

    if item.days_remaining < 0:
        return {"status": "skipped", "reason": "already_expired"}

    if item.days_remaining > prefs.days_before_expiry:
        return {"status": "skipped", "reason": "outside_threshold"}

    current_hour_utc = datetime.utcnow().hour
    if _is_in_quiet_hours(prefs, current_hour_utc):
        return {"status": "skipped", "reason": "quiet_hours"}

    dispatch = _create_dispatch(db, user_id, item.id, source)
    if not dispatch:
        return {"status": "skipped", "reason": "duplicate"}

    devices = db.query(DeviceToken).filter(
        and_(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True,
        )
    ).all()

    title, body, data = _build_expiry_payload(item)
    send_report = _send_payload_to_devices(
        db=db,
        devices=devices,
        title=title,
        body=body,
        data=data,
        source=source,
        user_id=user_id,
        item_id=item.id,
    )

    dispatch.status = send_report["status"]
    dispatch.sent_count = send_report["sent_count"]
    dispatch.failed_count = send_report["failed_count"]
    dispatch.invalid_tokens_count = send_report["invalid_tokens_count"]
    dispatch.failure_reason = send_report.get("reason")
    db.commit()

    return send_report


def send_test_push_to_self(
    db: Session,
    user_id: uuid.UUID,
    data: TestSendSelfRequest,
) -> dict:
    if settings.app_env == "production" or not settings.notifications_qa_endpoint_enabled:
        raise AppException(
            status_code=403,
            code=ErrorCode.UNAUTHORIZED,
            message="Endpoint QA deshabilitado en este entorno.",
        )

    devices = db.query(DeviceToken).filter(
        and_(
            DeviceToken.user_id == user_id,
            DeviceToken.is_active == True,
        )
    ).all()

    title = data.title or "⚠️ Alimentos próximos a vencer"
    body = data.body or "Push de prueba desde backend"
    payload_data = {
        "route": data.route,
        "item_id": data.item_id or "",
        "item_name": data.item_name or "",
        "days_remaining": str(data.days_remaining) if data.days_remaining is not None else "",
        "type": "expiry_alert",
    }

    report = _send_payload_to_devices(
        db=db,
        devices=devices,
        title=title,
        body=body,
        data=payload_data,
        source="qa",
        user_id=user_id,
        item_id=None,
    )
    db.commit()
    return report


def send_expiry_alerts(db: Session):
    """
    Tarea periódica — revisa todos los usuarios y envía alertas
    para productos que vencen dentro del umbral configurado.
    Esta función será llamada por APScheduler cada hora.
    """
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.push_enabled == True
    ).all()

    for pref in preferences:
        expiry_threshold = date.today() + timedelta(days=pref.days_before_expiry)
        expiring_items = db.query(InventoryItem).filter(
            and_(
                InventoryItem.user_id == pref.user_id,
                InventoryItem.status == "active",
                InventoryItem.expiry_date <= expiry_threshold,
            )
        ).all()

        for item in expiring_items:
            process_item_expiry_notification(
                db=db,
                user_id=pref.user_id,
                item=item,
                source="scheduler",
            )
