from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.common.dependencies import get_current_user
from app.auth.models import User
from app.sync import service as sync_service
from app.sync.schemas import SyncPushRequest, SyncPushResponse, SyncPullResponse

router = APIRouter(prefix="/api/v1/sync", tags=["Sincronización"])


@router.post("/push", response_model=SyncPushResponse)
def push_changes(
    data: SyncPushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recibe los cambios pendientes del cliente y los aplica al servidor."""
    return sync_service.push_changes(db, current_user.id, data)


@router.get("/pull", response_model=SyncPullResponse)
def pull_changes(
    since: datetime = Query(..., description="ISO 8601 — retorna cambios posteriores a este timestamp"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retorna los cambios del servidor desde el último sync del cliente."""
    return sync_service.pull_changes(db, current_user.id, since)
