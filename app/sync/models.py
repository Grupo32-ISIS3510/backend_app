import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    entity_type      = Column(String(50), nullable=False)         # 'inventory_item'
    entity_id        = Column(UUID(as_uuid=True), nullable=False)  # id del objeto sincronizado
    operation        = Column(String(20), nullable=False)          # 'create','update','delete'
    payload          = Column(JSON, nullable=False)                # snapshot del objeto
    client_timestamp = Column(DateTime, nullable=False)            # cuándo ocurrió en el cliente
    server_timestamp = Column(DateTime, default=datetime.utcnow)   # cuándo llegó al servidor
    is_conflict      = Column(Boolean, default=False)
    resolved_at      = Column(DateTime, nullable=True)
