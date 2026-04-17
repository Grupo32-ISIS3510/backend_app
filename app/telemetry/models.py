import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id         = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    timestamp       = Column(DateTime, nullable=False)
    success         = Column(Boolean, nullable=False)
    failure_reason  = Column(String(255), nullable=True)
    products_detected = Column(Integer, nullable=False, default=0)
    duration_ms     = Column(Integer, nullable=False, default=0)
    received_at     = Column(DateTime, default=datetime.utcnow)
