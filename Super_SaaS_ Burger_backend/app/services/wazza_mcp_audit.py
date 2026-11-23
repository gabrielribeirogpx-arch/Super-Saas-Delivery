"""Privacy-minimized audit records for Wazza MCP tool execution."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.wazza_mcp import WazzaMcpAuditLog, WazzaMcpCredential


VALID_RISKS = frozenset({"read", "write", "destructive"})
VALID_OUTCOMES = frozenset({"success", "denied", "error"})


def record_tool_audit(
    db: Session,
    *,
    credential: WazzaMcpCredential,
    request_id: str,
    tool_name: str,
    risk: str,
    outcome: str,
    duration_ms: int,
    conversation_id: str | None = None,
    error_code: str | None = None,
    argument_keys: Iterable[str] = (),
) -> WazzaMcpAuditLog:
    normalized_request_id = request_id.strip()
    normalized_tool_name = tool_name.strip()
    normalized_conversation_id = conversation_id.strip() if conversation_id else None
    if not normalized_request_id or len(normalized_request_id) > 128:
        raise ValueError("invalid_wazza_mcp_request_id")
    if not normalized_tool_name or len(normalized_tool_name) > 100:
        raise ValueError("invalid_wazza_mcp_tool_name")
    if normalized_conversation_id and len(normalized_conversation_id) > 128:
        raise ValueError("invalid_wazza_mcp_conversation_id")
    if risk not in VALID_RISKS or outcome not in VALID_OUTCOMES:
        raise ValueError("invalid_wazza_mcp_audit_classification")
    if duration_ms < 0:
        raise ValueError("invalid_wazza_mcp_duration")
    if error_code is not None and len(error_code) > 80:
        raise ValueError("invalid_wazza_mcp_error_code")

    # Store schema shape only. Values may contain PII, credentials or free text.
    keys = sorted({str(key).strip() for key in argument_keys if str(key).strip()})
    if any(len(key) > 100 for key in keys) or len(keys) > 100:
        raise ValueError("invalid_wazza_mcp_argument_keys")

    entry = WazzaMcpAuditLog(
        tenant_id=credential.tenant_id,
        credential_id=credential.id,
        request_id=normalized_request_id,
        conversation_id=normalized_conversation_id,
        tool_name=normalized_tool_name,
        risk=risk,
        outcome=outcome,
        error_code=error_code,
        duration_ms=duration_ms,
        argument_keys_json=keys,
    )
    db.add(entry)
    return entry
