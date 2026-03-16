from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.notifications import service as notif_service
from app.notifications.schemas import (
    DeviceTokenRegister,
    NotificationPreferenceUpdate,
    NotificationPreferenceResponse
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notificaciones"])


@router.post("/device", status_code=201)
def register_device(
    data: DeviceTokenRegister,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notif_service.register_device_token(db, current_user.id, data)
    return {"status": "success", "message": "Dispositivo registrado correctamente"}


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notif_service.get_or_create_preferences(db, current_user.id)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    data: NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return notif_service.update_preferences(db, current_user.id, data)