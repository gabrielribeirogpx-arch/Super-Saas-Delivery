from __future__ import annotations

PRODUCTION_AREAS = {
    "COZINHA",
    "BAR",
    "BEBIDAS",
    "CAIXA",
}


def normalize_production_area(area: str | None, *, default: str = "COZINHA") -> str:
    value = (area or default).strip().upper()
    if value not in PRODUCTION_AREAS:
        raise ValueError("Área de produção inválida")
    return value
