import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, Date, Float, ForeignKey
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


class ExpiryAccuracyEvent(Base):
    __tablename__ = "expiry_accuracy_events"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id             = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    timestamp           = Column(DateTime, nullable=False)
    category            = Column(String(100), nullable=False, index=True)
    ocr_detected_date   = Column(Boolean, nullable=False)
    ocr_date            = Column(Date, nullable=True)
    user_confirmed_date = Column(Date, nullable=False)
    accurate            = Column(Boolean, nullable=False)
    received_at         = Column(DateTime, default=datetime.utcnow)


class ScreenEvent(Base):
    __tablename__ = "screen_events"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    timestamp   = Column(DateTime, nullable=False)
    screen_name = Column(String(100), nullable=False, index=True)
    event_type  = Column(String(20), nullable=False)
    exit_reason = Column(String(100), nullable=True)
    dwell_time_ms = Column(Integer, nullable=False, default=0)
    received_at = Column(DateTime, default=datetime.utcnow)


# ── T3.1 — Feature Usage Events ──────────────────────────────
# Cada apertura/uso de una feature por parte de un usuario.
# Alimenta el dashboard con la distribución semanal de frecuencia
# de uso por feature entre usuarios activos.

class FeatureUsageEvent(Base):
    __tablename__ = "feature_usage_events"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    feature     = Column(String(50), nullable=False, index=True)
    timestamp   = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
