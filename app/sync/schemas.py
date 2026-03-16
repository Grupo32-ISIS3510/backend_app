from datetime import datetime
from typing import Any

from pydantic import BaseModel, UUID4


class SyncChange(BaseModel):
    entity_type: str         # 'inventory_item'
    entity_id: UUID4
    operation: str           # 'create' | 'update' | 'delete'
    payload: dict[str, Any]  # snapshot del objeto en el momento del cambio
    client_timestamp: datetime


class SyncPushRequest(BaseModel):
    changes: list[SyncChange]


class SyncPushResponse(BaseModel):
    processed: list[str]     # UUIDs procesados exitosamente
    conflicts: list[str]     # UUIDs donde el servidor tenía una versión más reciente
    server_timestamp: datetime


class SyncPullResponse(BaseModel):
    changes: list[SyncChange]
    server_timestamp: datetime
    has_more: bool
