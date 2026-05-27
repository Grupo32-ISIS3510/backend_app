import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name          = Column(String(100), nullable=False)
    category      = Column(String(50), nullable=True)   # 'dairy','fruits','vegetables','meat'...
    quantity      = Column(Numeric(10, 2), nullable=False, default=1)
    unit          = Column(String(20), nullable=True)   # 'kg', 'units', 'liters'...
    unit_price    = Column(Numeric(10, 2), nullable=True)
    purchase_date = Column(Date, nullable=False)
    expiry_date   = Column(Date, nullable=False)
    status        = Column(String(20), nullable=False, default="active")  # active/consumed/discarded
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relación con los eventos — permite acceder a item.events desde Python
    events        = relationship("InventoryEvent", back_populates="item")

    @property
    def days_remaining(self) -> int:
        """Calcula los días restantes hasta el vencimiento en tiempo real."""
        return (self.expiry_date - datetime.utcnow().date()).days


class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_id     = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False)
    event_type  = Column(String(20), nullable=False)  # registered/consumed/discarded/expired
    reason      = Column(String(50), nullable=True)   # motivo del descarte
    quantity    = Column(Numeric(10, 2), nullable=True)
    unit_price  = Column(Numeric(10, 2), nullable=True)
    # T3.2: recipe responsable de un consumo (NULL si fue manual / no vino de cocinar una receta)
    recipe_id   = Column(UUID(as_uuid=True), ForeignKey("recipes.id"), nullable=True, index=True)
    occurred_at = Column(DateTime, default=datetime.utcnow)

    item        = relationship("InventoryItem", back_populates="events")