from __future__ import annotations

TEMPLATES: dict[str, str] = {
    "order_edited": "Olá {customer_name}! Seu pedido #{order_number} foi atualizado. Novo total: {order_total}.",
    "order_canceled": "Olá {customer_name}! Seu pedido #{order_number} foi cancelado.",
    "order_confirmed": (
        "Olá {customer_name}! ✅ Seu pedido #{order_number} foi confirmado. "
        "Total: {order_total}. Tempo estimado: {estimated_time}."
    ),
    "order_in_preparation": (
        "Olá {customer_name}! 👨‍🍳 Seu pedido #{order_number} está em preparo. "
        "Tempo estimado: {estimated_time}."
    ),
    "order_ready": (
        "Olá {customer_name}! 🍔✅ Seu pedido #{order_number} está pronto. "
        "Total: {order_total}."
    ),
    "order_out_for_delivery": (
        "Olá {customer_name}! 🛵 Seu pedido #{order_number} saiu para entrega. "
        "Tempo estimado: {estimated_time}.{tracking_line}"
    ),
    "order_delivered": (
        "Olá {customer_name}! 📦 Pedido #{order_number} entregue. "
        "Total: {order_total}. Obrigado pela preferência!"
    ),
}
