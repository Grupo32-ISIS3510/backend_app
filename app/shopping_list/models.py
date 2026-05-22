from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class ShoppingItem(Base):
    """Item de la lista de compras del usuario.

    El `id` se acepta tal como lo envía el cliente (formato 'sl_<timestamp>')
    para preservar la correspondencia con la cola offline del front
    (SQLite local → backend). Así una operación encolada offline puede
    sincronizarse luego con el mismo identificador.
    """

    __tablename__ = "shopping_list_items"

    id          = Column(String(64), primary_key=True)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name        = Column(String(100), nullable=False)
    category    = Column(String(50), nullable=False, default="Otros")
    quantity    = Column(Numeric(10, 2), nullable=False, default=1)
    unit        = Column(String(20), nullable=True)
    purchased   = Column(Boolean, nullable=False, default=False)
    source      = Column(String(20), nullable=False, default="manual")   # manual | consumed | recipe
    source_ref  = Column(String(64), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
