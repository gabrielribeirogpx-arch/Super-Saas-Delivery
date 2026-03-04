from __future__ import annotations

from typing import Any

GLOBAL_ETA_FALLBACK_SECONDS = 1800


def _coerce_eta_seconds(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        parsed = int(value)
        return parsed if parsed > 0 else None

    if isinstance(value, str):
        raw = value.strip().lower()
        if not raw:
            return None

        if raw.endswith("min"):
            raw = raw[:-3].strip()

        if raw.endswith("m"):
            raw = raw[:-1].strip()

        if raw.endswith("s"):
            raw = raw[:-1].strip()
            if raw.isdigit():
                parsed = int(raw)
                return parsed if parsed > 0 else None
            return None

        if raw.isdigit():
            parsed = int(raw)
            if parsed <= 0:
                return None
            if parsed <= 120:
                return parsed * 60
            return parsed

    return None


def _read_candidate(container: Any, attribute_names: tuple[str, ...]) -> int | None:
    for attribute_name in attribute_names:
        parsed = _coerce_eta_seconds(getattr(container, attribute_name, None))
        if parsed is not None:
            return parsed
    return None


def calculate_eta(order: Any, mode: str = "static") -> int:
    if mode == "gps":
        return calculate_eta_from_distance(order)
    return calculate_eta_static(order)


def calculate_eta_static(order: Any) -> int:
    tenant = getattr(order, "tenant", None)
    if tenant is not None:
        tenant_average = _read_candidate(
            tenant,
            (
                "average_delivery_time_seconds",
                "average_delivery_time",
                "estimated_delivery_time_seconds",
                "estimated_delivery_time",
            ),
        )
        if tenant_average is not None:
            return tenant_average

        tenant_config = getattr(tenant, "config", None)
        if tenant_config is not None:
            tenant_config_eta = _read_candidate(
                tenant_config,
                (
                    "delivery_eta_seconds",
                    "delivery_time_seconds",
                    "default_delivery_eta_seconds",
                    "default_eta_seconds",
                    "estimated_prep_time",
                ),
            )
            if tenant_config_eta is not None:
                return tenant_config_eta

    order_config = getattr(order, "tenant_config", None)
    if order_config is not None:
        order_config_eta = _read_candidate(
            order_config,
            (
                "delivery_eta_seconds",
                "delivery_time_seconds",
                "default_delivery_eta_seconds",
                "default_eta_seconds",
                "estimated_prep_time",
            ),
        )
        if order_config_eta is not None:
            return order_config_eta

    return GLOBAL_ETA_FALLBACK_SECONDS


def calculate_eta_from_distance(order: Any) -> int:
    raise NotImplementedError("Distance-based ETA is not implemented yet")
