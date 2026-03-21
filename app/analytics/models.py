import uuid
from datetime import datetime
from sqlalchemy import Column, String, BigInteger, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AnalyticsEvent(Base):
    """
    Modelo para almacenar eventos de analytics del usuario.
    Permite trackear interacciones para análisis de comportamiento y mejoras.
    """
    __tablename__ = "analytics_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)  # Unix timestamp en milisegundos
    properties = Column(JSON, nullable=True)  # Propiedades adicionales del evento
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relación con User
    user = relationship("User", back_populates="analytics_events")
