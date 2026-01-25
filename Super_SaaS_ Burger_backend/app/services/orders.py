import json
from sqlalchemy.orm import Session
from app.models.order import Order
from app.models.conversation import Conversation


def _get(d: dict, *keys, default=""):
    """Tenta várias chaves possíveis."""
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def create_order_from_conversation(
    db: Session,
    tenant_id: int,
    convo: Conversation,
    contact_name: str | None = None
) -> Order:
    """
    Cria um pedido no banco a partir do JSON convo.dados.
    Robusto: tenta várias chaves e cai em defaults.
    """
    # dados do FSM ficam aqui (JSON)
    dados = {}
    try:
        dados = json.loads(convo.dados or "{}")
        if not isinstance(dados, dict):
            dados = {}
    except Exception:
        dados = {}

    itens = _get(dados, "itens", "pedido", "order_items", default="").strip()
    tipo_entrega = _get(dados, "tipo_entrega", "modo", "entrega", default="").strip()
    endereco = _get(dados, "endereco", "endereço", "address", default="").strip()
    observacao = _get(dados, "observacao", "observação", "obs", default="").strip()
    forma_pagamento = _get(dados, "forma_pagamento", "pagamento", "payment", default="").strip()
    total_cents = _get(dados, "total_cents", "total", "valor_total", default=0)
    try:
        total_cents = int(total_cents)
    except Exception:
        total_cents = 0

    # Nome: vem do WhatsApp (contact_name). Se não tiver, tenta no JSON.
    cliente_nome = (contact_name or _get(dados, "cliente_nome", "nome", default="")).strip()

    order = Order(
        tenant_id=tenant_id,
        cliente_nome=cliente_nome or "",
        cliente_telefone=convo.telefone,

        itens=itens or "(não informado)",
        endereco=endereco or "",
        observacao=observacao or "",
        tipo_entrega=(tipo_entrega or "").upper(),
        forma_pagamento=(forma_pagamento or "").upper(),

        status="RECEBIDO",
        valor_total=total_cents,
    )

    db.add(order)
    db.commit()
    db.refresh(order)
    return order
