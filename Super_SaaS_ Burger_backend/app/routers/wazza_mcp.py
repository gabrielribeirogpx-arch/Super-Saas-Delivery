"""Minimal JSON-RPC MCP endpoint for the Wazza read-only rollout."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import config
from app.core.database import get_db
from app.core.rate_limiter import InMemoryRateLimiterService
from app.services.wazza_mcp_audit import record_tool_audit
from app.services.wazza_mcp_auth import WazzaMcpAuthError, authenticate_credential, require_scope
from app.services.wazza_mcp_identity import (
    CONTEXT_HEADER,
    SIGNATURE_HEADER,
    WazzaMcpIdentityError,
    verify_customer_identity,
)
from app.services.wazza_mcp_read_tools import McpReadToolError, TOOL_DEFINITIONS, execute_read_tool, public_tool_list


router = APIRouter(prefix="/api/integrations/wazza", tags=["wazza-mcp"])
MAX_BODY_BYTES = 65_536
_rate_limiter = InMemoryRateLimiterService(limit=120, window_seconds=60)


def _error(request_id: Any, code: int, message: str, *, status_code: int = 200, headers: dict[str, str] | None = None):
    return JSONResponse(
        status_code=status_code,
        content={"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        headers=headers,
    )


def _result(request_id: Any, value: dict[str, Any]):
    return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": value})


def _bearer_token(request: Request) -> str:
    value = request.headers.get("Authorization", "")
    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        raise WazzaMcpAuthError("invalid_credential")
    return token.strip()


def _tool_content(name: str, data: dict[str, Any], *, risk: str = "read") -> dict[str, Any]:
    structured = {"ok": True, "tool": name, "type": "read_result" if risk == "read" else "write_result", "data": data}
    return {
        "content": [{"type": "text", "text": json.dumps(structured, ensure_ascii=False, separators=(",", ":"))}],
        "structuredContent": structured,
        "isError": False,
    }


@router.post("/mcp")
async def wazza_mcp(request: Request, db: Session = Depends(get_db)):
    request_id: Any = None
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
        return _error(None, -32600, "Requisição muito grande.", status_code=413)
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_BYTES:
        return _error(None, -32600, "Requisição muito grande.", status_code=413)
    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        return _error(None, -32700, "JSON inválido.", status_code=400)
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0" or "id" not in payload:
        return _error(payload.get("id") if isinstance(payload, dict) else None, -32600, "Requisição JSON-RPC inválida.", status_code=400)
    request_id = payload.get("id")
    if isinstance(request_id, bool) or not isinstance(request_id, (str, int)) or len(str(request_id)) > 128:
        return _error(None, -32600, "Identificador JSON-RPC inválido.", status_code=400)
    try:
        credential = authenticate_credential(db, _bearer_token(request))
    except WazzaMcpAuthError as exc:
        if exc.code == "integration_disabled":
            return _error(request_id, -32000, "Integração indisponível.", status_code=503)
        return _error(
            request_id,
            -32001,
            "Credencial inválida.",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        customer_identity = verify_customer_identity(
            credential=credential,
            encoded_context=request.headers.get(CONTEXT_HEADER),
            encoded_signature=request.headers.get(SIGNATURE_HEADER),
            request_id=str(request_id),
        )
    except WazzaMcpIdentityError:
        db.rollback()
        return _error(request_id, -32005, "Identidade do cliente inválida.", status_code=401)
    request.state.wazza_customer_identity = customer_identity

    decision = _rate_limiter.check(tenant_id=f"{credential.tenant_id}:{credential.key_id}", endpoint="mcp")
    rate_headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if not decision.allowed:
        db.commit()
        return _error(
            request_id,
            -32002,
            "Limite de requisições excedido.",
            status_code=429,
            headers={**rate_headers, "Retry-After": str(decision.retry_after_seconds)},
        )

    method = payload.get("method")
    params = payload.get("params") or {}
    if method == "initialize":
        db.commit()
        response = _result(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "fomizero-wazza", "version": "1.0.0"},
            },
        )
        response.headers.update(rate_headers)
        return response
    if method == "tools/list":
        db.commit()
        response = _result(request_id, {"tools": public_tool_list(set(credential.scopes_json or []))})
        response.headers.update(rate_headers)
        return response
    if method != "tools/call" or not isinstance(params, dict):
        db.commit()
        return _error(request_id, -32601, "Método não encontrado.")

    name = str(params.get("name") or "").strip()
    arguments = params.get("arguments", {})
    started = time.monotonic()
    outcome = "error"
    error_code: str | None = None
    try:
        definition = TOOL_DEFINITIONS.get(name)
        if definition is None:
            raise McpReadToolError("tool_not_found", "Ferramenta não encontrada.")
        require_scope(credential, definition["scope"])
        if not isinstance(arguments, dict):
            raise McpReadToolError("invalid_arguments", "Os argumentos devem formar um objeto.")
        data = execute_read_tool(
            db,
            credential.tenant_id,
            name,
            arguments,
            customer_identity=customer_identity,
        )
        outcome = "success"
        result = _tool_content(name, data, risk=definition.get("risk", "read"))
    except WazzaMcpAuthError:
        outcome = "denied"
        error_code = "insufficient_scope"
        result = None
    except ValidationError:
        error_code = "invalid_arguments"
        result = None
    except McpReadToolError as exc:
        error_code = exc.code
        result = None

    duration_ms = max(0, int((time.monotonic() - started) * 1000))
    record_tool_audit(
        db,
        credential=credential,
        request_id=str(request_id),
        conversation_id=customer_identity.conversation_id if customer_identity else None,
        tool_name=(name or "unknown")[:100],
        risk=(definition.get("risk", "read") if "definition" in locals() and definition else "read"),
        outcome=outcome,
        error_code=error_code,
        duration_ms=duration_ms,
        argument_keys=[str(key)[:100] for key in list(arguments.keys())[:100]] if isinstance(arguments, dict) else (),
    )
    db.commit()
    if result is None:
        code = (
            -32602
            if error_code == "invalid_arguments"
            else -32003
            if error_code == "insufficient_scope"
            else -32006
            if error_code == "customer_identity_required"
            else -32004
        )
        response = _error(request_id, code, "A ferramenta não pôde concluir a consulta.")
    else:
        response = _result(request_id, result)
    response.headers.update(rate_headers)
    return response
