from __future__ import annotations

from fastapi import Request


def get_current_tenant_id(request: Request) -> int | None:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is not None:
        try:
            return int(tenant_id)
        except (TypeError, ValueError):
            return None

    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return None

    tenant_id_from_tenant = getattr(tenant, "id", None)
    if tenant_id_from_tenant is None:
        return None

    try:
        return int(tenant_id_from_tenant)
    except (TypeError, ValueError):
        return None


def tenant_filter(query, model, request: Request):
    tenant_id = get_current_tenant_id(request)
    if tenant_id is None:
        return query

    model_tenant_id = getattr(model, "tenant_id", None)
    if model_tenant_id is None:
        return query

    return query.filter(model_tenant_id == tenant_id)
