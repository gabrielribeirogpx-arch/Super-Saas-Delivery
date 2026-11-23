from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.models.tenant import Tenant
from app.models.wazza_mcp import WazzaMcpAuditLog, WazzaMcpCredential
from app.services.wazza_mcp_audit import record_tool_audit
from app.services.wazza_mcp_auth import (
    WazzaMcpAuthError,
    authenticate_credential,
    issue_credential,
    require_scope,
    revoke_credential,
)


NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sessions():
    engine = sa.create_engine("sqlite:///:memory:")
    @sa.event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Tenant.__table__.create(engine)
    WazzaMcpCredential.__table__.create(engine)
    WazzaMcpAuditLog.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all(
            [
                Tenant(id=1, name="First", business_name="First", slug="first"),
                Tenant(id=2, name="Second", business_name="Second", slug="second"),
            ]
        )
        db.commit()
    yield factory
    engine.dispose()


def _issue(db: Session, tenant_id: int = 1, scopes=("menu:read", "order:read")):
    issued = issue_credential(
        db,
        tenant_id=tenant_id,
        name="Wazza principal",
        scopes=scopes,
        now=NOW,
    )
    db.commit()
    return issued


def test_issued_secret_is_returned_once_and_only_hash_is_persisted(sessions):
    with sessions() as db:
        issued = _issue(db)
        stored = db.get(WazzaMcpCredential, issued.credential.id)

        assert issued.token.startswith(f"fmz_mcp_{stored.key_id}.")
        assert issued.token not in json.dumps({"hash": stored.token_hash, "scopes": stored.scopes_json})
        assert len(stored.token_hash) == 64
        assert stored.scopes_json == ["menu:read", "order:read"]


def test_authentication_binds_tenant_from_credential_and_updates_last_use(sessions):
    with sessions() as db:
        first = _issue(db, tenant_id=1)
        second = _issue(db, tenant_id=2)

        authenticated = authenticate_credential(db, first.token, enabled=True, now=NOW + timedelta(minutes=1))
        assert authenticated.tenant_id == 1
        assert authenticated.key_id != second.credential.key_id
        assert authenticated.last_used_at == NOW + timedelta(minutes=1)


def test_integration_is_fail_closed_before_token_lookup(sessions):
    with sessions() as db:
        issued = _issue(db)
        with pytest.raises(WazzaMcpAuthError, match="integration_disabled"):
            authenticate_credential(db, issued.token, enabled=False, now=NOW)
        db.refresh(issued.credential)
        assert issued.credential.last_used_at is None


@pytest.mark.parametrize("raw_token", ["", "invalid", "fmz_mcp_bad.secret", "fmz_mcp_0000000000000000.fakefakefakefakefakefakefakefake"])
def test_malformed_and_unknown_tokens_share_generic_error(sessions, raw_token):
    with sessions() as db, pytest.raises(WazzaMcpAuthError) as error:
        authenticate_credential(db, raw_token, enabled=True, now=NOW)
    assert error.value.code == "invalid_credential"


def test_revoked_and_expired_credentials_share_generic_error(sessions):
    with sessions() as db:
        revoked = _issue(db)
        assert revoke_credential(revoked.credential, now=NOW + timedelta(minutes=1)) is True
        assert revoke_credential(revoked.credential, now=NOW + timedelta(minutes=2)) is False
        db.commit()
        with pytest.raises(WazzaMcpAuthError) as revoked_error:
            authenticate_credential(db, revoked.token, enabled=True, now=NOW + timedelta(minutes=3))

        expired = issue_credential(
            db,
            tenant_id=1,
            name="Expiring",
            scopes=("menu:read",),
            expires_at=NOW + timedelta(minutes=5),
            now=NOW,
        )
        db.commit()
        with pytest.raises(WazzaMcpAuthError) as expired_error:
            authenticate_credential(db, expired.token, enabled=True, now=NOW + timedelta(minutes=5))

    assert revoked_error.value.code == expired_error.value.code == "invalid_credential"


def test_scopes_are_explicit_and_wildcards_are_rejected(sessions):
    with sessions() as db:
        issued = _issue(db, scopes=("menu:read",))
        require_scope(issued.credential, "menu:read")
        with pytest.raises(WazzaMcpAuthError, match="insufficient_scope"):
            require_scope(issued.credential, "order:read")
        with pytest.raises(ValueError, match="invalid_wazza_mcp_scopes"):
            issue_credential(db, tenant_id=1, name="Unsafe", scopes=("*",), now=NOW)


def test_audit_derives_tenant_from_credential_and_stores_only_argument_keys(sessions):
    with sessions() as db:
        issued = _issue(db)
        entry = record_tool_audit(
            db,
            credential=issued.credential,
            request_id="req-123",
            conversation_id="conversation-opaque-456",
            tool_name="menu_search_items",
            risk="read",
            outcome="success",
            duration_ms=18,
            argument_keys=("query", "limit", "query"),
        )
        db.commit()
        db.refresh(entry)

        assert entry.tenant_id == 1
        assert entry.credential_id == issued.credential.id
        assert entry.argument_keys_json == ["limit", "query"]
        serialized = json.dumps(entry.argument_keys_json)
        assert "hamburguer" not in serialized


def test_database_rejects_cross_tenant_audit_credential(sessions):
    with sessions() as db:
        first = _issue(db, tenant_id=1)
        db.add(
            WazzaMcpAuditLog(
                tenant_id=2,
                credential_id=first.credential.id,
                request_id="cross-tenant",
                tool_name="menu_search_items",
                risk="read",
                outcome="denied",
                duration_ms=0,
                argument_keys_json=[],
            )
        )
        with pytest.raises(sa.exc.IntegrityError):
            db.commit()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_id": "", "tool_name": "menu_search_items", "risk": "read", "outcome": "success", "duration_ms": 1},
        {"request_id": "req", "tool_name": "menu_search_items", "risk": "admin", "outcome": "success", "duration_ms": 1},
        {"request_id": "req", "tool_name": "menu_search_items", "risk": "read", "outcome": "unknown", "duration_ms": 1},
        {"request_id": "req", "tool_name": "menu_search_items", "risk": "read", "outcome": "success", "duration_ms": -1},
    ],
)
def test_invalid_audit_shape_fails_before_persistence(sessions, kwargs):
    with sessions() as db:
        issued = _issue(db)
        with pytest.raises(ValueError):
            record_tool_audit(db, credential=issued.credential, **kwargs)
