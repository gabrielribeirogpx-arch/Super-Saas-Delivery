"""Canonical order statuses shared by channel and lifecycle services."""

ALIASES = {
    "PENDING": "RECEBIDO",
    "PREPARING": "EM_PREPARO",
    "PREPARO": "EM_PREPARO",
    "PREPARANDO": "EM_PREPARO",
    "READY": "PRONTO",
    "READY_FOR_DELIVERY": "PRONTO",
    "OUT_FOR_DELIVERY": "SAIU_PARA_ENTREGA",
    "SAIU": "SAIU_PARA_ENTREGA",
    "DELIVERED": "ENTREGUE",
    "ASSIGNED": "DRIVER_ASSIGNED",
}


def canonical_status(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    return ALIASES.get(normalized, normalized)
