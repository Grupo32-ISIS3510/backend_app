import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email      = Column(String(255), unique=True, nullable=False, index=True)
    full_name  = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active  = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    location   = Column(String(100), nullable=True)  # para recomendaciones por clima
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con analytics events
    analytics_events = relationship("AnalyticsEvent", back_populates="user", cascade="all, delete-orphan")