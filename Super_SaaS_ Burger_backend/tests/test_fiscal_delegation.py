from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile
from app.models.tenant import Tenant
from app.routers import admin_fiscal, admin_focus, fiscal_delegation
from app.services.focus_companies import verify_existing_company


def test_fiscal_invite_is_scoped_revocable_and_expires(tmp_path, monkeypatch):
    monkeypatch.setenv("FOCUS_NFE_MASTER_TOKEN", "master")
    monkeypatch.setenv("FOCUS_NFCE_PILOT_NAMESPACE", "test")
    engine = create_engine(f"sqlite:///{tmp_path / 'delegate.db'}")
    Tenant.__table__.create(engine)
    FiscalProfile.__table__.create(engine)
    with Session(engine) as db:
        for tenant_id in (1, 2):
            db.add(Tenant(id=tenant_id, slug=f"test{tenant_id}"))
            db.add(FiscalProfile(
                tenant_id=tenant_id, cnpj="12345678000195", legal_name=f"Loja {tenant_id}",
                state_registration="123", state_code="SP", tax_regime=1,
            ))
        db.commit()

    def open_session():
        with Session(engine) as db:
            yield db

    app = FastAPI()
    app.include_router(admin_fiscal.router)
    app.include_router(admin_focus.router)
    app.include_router(fiscal_delegation.admin_router)
    app.include_router(fiscal_delegation.access_router)
    app.dependency_overrides[get_db] = open_session
    user = AdminUser(id=7, tenant_id=1, role="owner")

    def admin():
        from fastapi import HTTPException

        if user.active is False:
            raise HTTPException(401)
        return user

    app.dependency_overrides[require_admin_user] = admin
    verify = Mock(side_effect=[ValueError("secret"), 101, 101])
    monkeypatch.setattr(admin_focus, "verify_existing_company", verify)
    manage = "/api/admin/store/fiscal/delegation"
    access = "/api/fiscal-delegation"

    with TestClient(app) as client:
        assert client.get(access).status_code == 401
        assert client.post(manage + "?tenant_id=2").status_code == 403
        invite = client.post(manage)
        assert invite.headers["cache-control"] == "no-store"
        token = invite.json()["token"]
        delegated = {"X-Fiscal-Access": token}
        assert client.get(access + "?tenant_id=2", headers=delegated).json()["legal_name"] == "Loja 1"
        with Session(engine) as db:
            assert db.get(FiscalProfile, 1).delegate_digest != token

        user.active = False
        assert client.get("/api/admin/store/fiscal", headers=delegated).status_code == 401
        assert client.post(manage, headers=delegated).status_code == 401
        invalid = client.post(access + "/link", headers=delegated, json={"token": "secret"})
        assert invalid.status_code == 422 and "secret" not in invalid.text
        assert client.post(access + "/link?tenant_id=2", headers=delegated, json={"token": "valid"}).json() == {
            "connected": True
        }
        with Session(engine) as db:
            assert db.get(FiscalProfile, 1).focus_company_id == 101
            assert db.get(FiscalProfile, 2).focus_company_id is None
        user.active = True
        user.tenant_id = 2
        assert client.post("/api/admin/store/fiscal/focus/link", json={"token": "valid"}).status_code == 409
        assert client.delete(manage).status_code == 204
        assert client.get(access, headers=delegated).status_code == 200
        user.tenant_id = 1
        assert client.delete(manage).status_code == 204
        assert client.get(access, headers=delegated).status_code == 401
        fresh = client.post(manage).json()["token"]
        with Session(engine) as db:
            db.get(FiscalProfile, 1).delegate_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.commit()
        assert client.get(access, headers={"X-Fiscal-Access": fresh}).status_code == 401
    engine.dispose()


def test_focus_verifies_existing_company_using_cnpj_and_homologation_token():
    cnpj = "12345678000195"

    def lookup(request):
        assert request.method == "GET" and request.url.params["cnpj"] == cnpj
        return httpx.Response(200, json=[
            {"id": 8, "cnpj": "98765432000100", "token_homologacao": "other"},
            {"id": 9, "cnpj": cnpj, "token_homologacao": "proof", "token_producao": "production"},
        ])

    with httpx.Client(transport=httpx.MockTransport(lookup)) as client:
        assert verify_existing_company(client, "master", cnpj, "proof") == 9
        for token in ("other", "production", ""):
            with pytest.raises(ValueError):
                verify_existing_company(client, "master", cnpj, token)
