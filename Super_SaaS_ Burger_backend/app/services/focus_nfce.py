"""Prepare and submit a narrow NFC-e pilot to Focus homologation."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

import httpx
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

from app.models.fiscal_profile import FiscalProfile
from app.models.order import Order
from app.models.order_item import OrderItem

HOMOLOGATION_URL = "https://homologacao.focusnfe.com.br/v2/nfce"


class FiscalProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codigo_ncm: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]
    cfop: Annotated[str, StringConstraints(pattern=r"^5[0-9]{3}$")]
    icms_origem: Annotated[str, StringConstraints(pattern=r"^[0-8]$")]
    icms_situacao_tributaria: Annotated[str, StringConstraints(pattern=r"^(102|103|300|400)$")]
    pis_situacao_tributaria: Annotated[str, StringConstraints(pattern=r"^0[4-9]$")]
    cofins_situacao_tributaria: Annotated[str, StringConstraints(pattern=r"^0[4-9]$")]
    unidade_comercial: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{1,6}$")]


def money(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


def prepare_payload(
    db: Session, tenant_id: int, order_id: int, products: dict[int, FiscalProduct],
) -> dict:
    profile = db.get(FiscalProfile, tenant_id)
    if profile is None or profile.tax_regime != 1:
        raise ValueError("O piloto requer um emitente cadastrado no Simples Nacional (CRT 1).")
    order = db.query(Order).filter_by(id=order_id, tenant_id=tenant_id).one_or_none()
    if order is None:
        raise ValueError("Pedido não encontrado na loja piloto.")
    if (
        order.order_type != "table"
        or order.status not in {"ENTREGUE", "DELIVERED"}
        or (order.payment_method or order.forma_pagamento).strip().lower() not in {"cash", "dinheiro"}
        or order.delivery_fee
        or order.discount_amount
        or order.coupon_id
        or order.payment_change_for
        or order.change_for
    ):
        raise ValueError("Use um pedido de mesa concluído, pago em dinheiro sem troco, frete ou desconto.")

    lines = db.query(OrderItem).filter_by(order_id=order.id, tenant_id=tenant_id).order_by(OrderItem.id)
    items = []
    cents = 0
    for line in lines:
        product = products.get(line.menu_item_id)
        if product is None:
            raise ValueError(f"Dados fiscais ausentes para o produto {line.menu_item_id}.")
        if (
            line.quantity <= 0
            or line.unit_price_cents <= 0
            or line.subtotal_cents != line.quantity * line.unit_price_cents
            or line.modifiers
            or line.modifiers_json not in {None, "", "[]"}
        ):
            raise ValueError("Use somente itens com preço, quantidade e subtotal compatíveis e sem adicionais.")
        cents += line.subtotal_cents
        items.append({
            **product.model_dump(),
            "numero_item": len(items) + 1,
            "codigo_produto": str(line.menu_item_id),
            "descricao": (
                line.name[:120] if items
                else "NOTA FISCAL EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
            ),
            "unidade_tributavel": product.unidade_comercial,
            "quantidade_comercial": line.quantity,
            "quantidade_tributavel": line.quantity,
            "valor_unitario_comercial": money(line.unit_price_cents),
            "valor_unitario_tributavel": money(line.unit_price_cents),
            "valor_bruto": money(line.subtotal_cents),
        })
    if not items or cents != order.total_cents:
        raise ValueError("O total do pedido precisa corresponder ao total de seus itens.")
    return {
        "cnpj_emitente": profile.cnpj,
        "data_emissao": datetime.now(timezone.utc).isoformat(),
        "natureza_operacao": "VENDA AO CONSUMIDOR",
        "indicador_inscricao_estadual_destinatario": "9",
        "modalidade_frete": "9",
        "local_destino": "1",
        "presenca_comprador": "1",
        "items": items,
        "formas_pagamento": [{"forma_pagamento": "01", "valor_pagamento": money(cents)}],
    }


def submit_or_consult(client: httpx.Client, token: str, ref: str, payload: dict) -> dict:
    auth = (token, "")
    response = client.get(f"{HOMOLOGATION_URL}/{ref}", auth=auth)
    if response.status_code == 404:
        response = client.post(HOMOLOGATION_URL, params={"ref": ref}, auth=auth, json=payload)
    response.raise_for_status()
    result = response.json()
    if (
        not isinstance(result, dict)
        or result.get("ref") != ref
        or result.get("cnpj_emitente") != payload["cnpj_emitente"]
        or not isinstance(result.get("status"), str)
    ):
        raise ValueError("A Focus retornou uma resposta incompatível com o emitente e a referência.")
    return result
