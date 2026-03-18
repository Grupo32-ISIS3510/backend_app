import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_name  = Column(String(100), nullable=False)
    properties  = Column(JSON, nullable=True)
    session_id  = Column(String(100), nullable=True)
    platform    = Column(String(20), nullable=True)
    app_version = Column(String(20), nullable=True)
    occurred_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
