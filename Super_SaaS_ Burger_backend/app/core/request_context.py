from __future__ import annotations

from contextvars import ContextVar


_REQUEST_ID_CTX: ContextVar[str | None] = ContextVar("request_id", default=None)
_TENANT_ID_CTX: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_USER_ID_CTX: ContextVar[str | None] = ContextVar("user_id", default=None)


def set_request_context(
    *, request_id: str | None = None, tenant_id: str | None = None, user_id: str | None = None
) -> None:
    if request_id is not None:
        _REQUEST_ID_CTX.set(request_id)
    if tenant_id is not None:
        _TENANT_ID_CTX.set(tenant_id)
    if user_id is not None:
        _USER_ID_CTX.set(user_id)


def get_request_id() -> str | None:
    return _REQUEST_ID_CTX.get()


def get_tenant_id() -> str | None:
    return _TENANT_ID_CTX.get()


def get_user_id() -> str | None:
    return _USER_ID_CTX.get()


def clear_request_context() -> None:
    _REQUEST_ID_CTX.set(None)
    _TENANT_ID_CTX.set(None)
    _USER_ID_CTX.set(None)
