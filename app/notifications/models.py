import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    fcm_token   = Column(String(500), nullable=False)
    platform    = Column(String(20), nullable=False)   # 'android_kotlin', 'android_flutter', 'ios_flutter'
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    days_before_expiry  = Column(Integer, default=3)      # umbral de días para alertas
    quiet_hours_start   = Column(Integer, nullable=True)  # hora en formato 0-23, ej. 22 = 10pm
    quiet_hours_end     = Column(Integer, nullable=True)  # ej. 7 = 7am
    push_enabled        = Column(Boolean, default=True)
    created_at          = Column(DateTime, default=datetime.utcnow)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationDispatch(Base):
    __tablename__ = "notification_dispatches"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id               = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_id               = Column(UUID(as_uuid=True), nullable=True)
    notification_type     = Column(String(50), nullable=False)
    dedupe_key            = Column(String(200), nullable=False, unique=True, index=True)
    source                = Column(String(30), nullable=False, default="scheduler")
    status                = Column(String(20), nullable=False, default="processing")
    sent_count            = Column(Integer, nullable=False, default=0)
    failed_count          = Column(Integer, nullable=False, default=0)
    invalid_tokens_count  = Column(Integer, nullable=False, default=0)
    failure_reason        = Column(Text, nullable=True)
    created_at            = Column(DateTime, default=datetime.utcnow)