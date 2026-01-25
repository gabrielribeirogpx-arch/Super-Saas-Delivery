from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.core.database import Base

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    # Multi-tenant (por enquanto fixo em 1)
    tenant_id = Column(Integer, index=True, nullable=False)

    # Identificação do cliente
    cliente_nome = Column(String, default="", nullable=False)
    cliente_telefone = Column(String, index=True, nullable=False)

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
    status = Column(String, default="RECEBIDO", nullable=False)  # RECEBIDO / PREPARO / PRONTO

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
