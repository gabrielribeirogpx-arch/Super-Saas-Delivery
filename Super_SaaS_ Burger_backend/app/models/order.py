import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    # Multi-tenant (por enquanto fixo em 1)
    tenant_id = Column(Integer, index=True, nullable=False)

    # Identificação do cliente
    cliente_nome = Column(String, default="", nullable=False)
    cliente_telefone = Column(String, index=True, nullable=False)

    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    customer_name = Column(String(120), nullable=True)
    customer_phone = Column(String(30), nullable=True)
    delivery_address_json = Column(JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True)
    payment_method = Column(String(30), nullable=True)
    payment_change_for = Column(Numeric(10, 2), nullable=True)
    order_note = Column(Text, nullable=True)

    # Pedido
    itens = Column(Text, nullable=False)  # texto livre por enquanto
    endereco = Column(Text, default="", nullable=False)
    observacao = Column(Text, default="", nullable=False)
    tipo_entrega = Column(String, default="", nullable=False)   # ENTREGA / RETIRADA
    forma_pagamento = Column(String, default="", nullable=False) # PIX / CARTAO / DINHEIRO

    # opcional nesta fase (pode ficar 0/empty)
    valor_total = Column(Integer, default=0, nullable=False)  # em centavos, quando calcular
    total_cents = Column(Integer, default=0, nullable=False)
    items_json = Column(Text, default="", nullable=False)

    # Kanban
    status = Column(String, default="RECEBIDO", nullable=False)  # RECEBIDO / EM_PREPARO / PRONTO / SAIU_PARA_ENTREGA / ENTREGUE
    production_ready_areas_json = Column(Text, default="[]", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("OrderPayment", back_populates="order", cascade="all, delete-orphan")
