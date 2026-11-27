import json
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.fiscal_profile import FiscalProfile
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.tenant import Tenant
from app.services.focus_nfce import FiscalProduct, prepare_payload, submit_or_consult


def test_pilot_builds_only_eligible_orders_from_the_selected_store():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Tenant(id=1, slug="fiscal-test"))
        db.add(FiscalProfile(tenant_id=1, cnpj="12345678000195", legal_name="Teste",
                             state_registration="123", state_code="SP", tax_regime=1))
        order = Order(
            id=123, tenant_id=1, order_type="table", status="ENTREGUE",
            cliente_telefone="", itens="", forma_pagamento="DINHEIRO", total_cents=2598,
        )
        db.add(order)
        db.add(OrderItem(
            order_id=123, tenant_id=1, menu_item_id=7, name="Item de teste",
            quantity=2, unit_price_cents=1299, subtotal_cents=2598,
        ))
        db.commit()
        products = {7: FiscalProduct(
            codigo_ncm="19059090", cfop="5102", icms_origem="0",
            icms_situacao_tributaria="102", pis_situacao_tributaria="07",
            cofins_situacao_tributaria="07", unidade_comercial="UN",
        )}
        with pytest.raises(ValueError, match="Pedido não encontrado"):
            prepare_payload(db, 1, 124, products)
        with pytest.raises(ValueError, match="Dados fiscais ausentes"):
            prepare_payload(db, 1, 123, {})
        payload = prepare_payload(db, 1, 123, products)
        assert payload["cnpj_emitente"] == "12345678000195"
        assert payload["items"][0]["valor_bruto"] == "25.98"
        assert payload["items"][0]["descricao"].endswith("SEM VALOR FISCAL")
        assert payload["formas_pagamento"] == [{"forma_pagamento": "01", "valor_pagamento": "25.98"}]
        order.discount_amount = 1
        with pytest.raises(ValueError, match="sem troco, frete ou desconto"):
            prepare_payload(db, 1, 123, products)
    engine.dispose()


def test_pilot_uses_only_homologation_and_consults_before_reissuing():
    payload = {"cnpj_emitente": "12345678000195"}
    ref = "FZstageT1O123"
    authorized = {**payload, "ref": ref, "status": "autorizado"}
    replies = iter([
        httpx.Response(404, json={"codigo": "nao_encontrado"}),
        httpx.Response(201, json=authorized),
        httpx.Response(200, json=authorized),
        httpx.Response(403),
    ])

    def handle(request):
        assert request.url.host == "homologacao.focusnfe.com.br"
        assert request.headers["authorization"] == "Basic dG9rZW46"
        if request.method == "POST":
            assert request.url.params["ref"] == ref
            assert json.loads(request.content) == payload
        else:
            assert request.url.path == f"/v2/nfce/{ref}"
        return next(replies)

    handler = Mock(side_effect=handle)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert submit_or_consult(client, "token", ref, payload) == authorized
        assert submit_or_consult(client, "token", ref, payload) == authorized
        with pytest.raises(httpx.HTTPStatusError):
            submit_or_consult(client, "token", ref, payload)
    assert [call.args[0].method for call in handler.call_args_list] == ["GET", "POST", "GET", "GET"]
