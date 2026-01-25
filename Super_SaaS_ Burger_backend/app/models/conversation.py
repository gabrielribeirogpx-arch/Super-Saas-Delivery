from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)

    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    telefone = Column(String, index=True)

    estado = Column(String, default="START")

    # dados coletados pelo FSM
    dados = Column(Text, default="{}")  # JSON serializado

    # evita criar pedidos duplicados
    last_order_id = Column(Integer, nullable=True)
