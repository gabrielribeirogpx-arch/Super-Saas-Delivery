"""Conjunto de dados reutilizável para cenários de teste backend."""

HAPPY_PATH_ADMIN = {
    "id": 7,
    "tenant_id": 1,
    "email": "admin@example.com",
    "name": "Admin",
    "role": "admin",
    "active": True,
    "password_hash": "hashed",
}

HAPPY_PATH_ORDER_PAYLOAD = {
    "cliente_nome": "João",
    "cliente_telefone": "11999990000",
    "itens": [
        {
            "menu_item_id": 101,
            "nome": "Burger Classic",
            "qtd": 2,
            "preco": 18.5,
            "modifiers": [{"name": "Bacon", "price_cents": 300}],
        }
    ],
    "endereco": "Rua Principal, 100",
    "observacao": "Sem cebola",
    "tipo_entrega": "delivery",
    "forma_pagamento": "pix",
    "valor_total": 40.0,
}

TENANT_ACCESS_DENIED = {
    "request_tenant_id": 2,
    "admin_tenant_id": 1,
    "expected_status_code": 403,
    "expected_detail": "Tenant não autorizado",
}

PAYMENT_HAPPY_PATH = {
    "method": "pix",
    "amount_cents": 4000,
    "fee_cents": 0,
    "status": "paid",
}

PAYMENT_ACCESS_DENIED = {
    "order_tenant_id": 2,
    "user_tenant_id": 1,
    "expected_status_code": 403,
    "expected_detail": "Sem permissão para este pedido",
}
