from contextlib import contextmanager
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile
from app.models.tenant import Tenant
from app.routers import admin_fiscal, admin_focus


def test_connect_and_issue_only_for_profile_bound_to_the_session(tmp_path, monkeypatch):
    monkeypatch.setenv("FOCUS_NFE_MASTER_TOKEN", "master")
    monkeypatch.setenv("FOCUS_NFCE_PILOT_NAMESPACE", "test")
    engine = create_engine(f"sqlite:///{tmp_path / 'fiscal.db'}")
    Tenant.__table__.create(engine)
    FiscalProfile.__table__.create(engine)
    profile = dict(
        cnpj="12345678000195", legal_name="Restaurante", state_registration="123",
        state_code="SP", tax_regime=1,
    )
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="one"), Tenant(id=2, slug="two")])
        db.add(FiscalProfile(tenant_id=1, **profile))
        db.commit()

    @contextmanager
    def fake_http(**kwargs):
        yield "http"

    monkeypatch.setattr(admin_focus.httpx, "Client", fake_http)
    create = Mock(return_value=42)
    token = Mock(return_value="homologation")
    emit = Mock(return_value={"status": "autorizado", "token_producao": "never-return"})
    prepare = Mock(return_value={"cnpj_emitente": profile["cnpj"]})
    monkeypatch.setattr(admin_focus, "create_company", create)
    monkeypatch.setattr(admin_focus, "get_homologation_token", token)
    monkeypatch.setattr(admin_focus, "prepare_payload", prepare)
    monkeypatch.setattr(admin_focus, "submit_or_consult", emit)

    user = AdminUser(id=7, tenant_id=1, role="owner")
    app = FastAPI()
    app.include_router(admin_fiscal.router)
    app.include_router(admin_focus.router)

    def open_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = open_session
    app.dependency_overrides[require_admin_user] = lambda: user
    path = "/api/admin/store/fiscal/focus"
    form = dict(
        logradouro="Rua", numero="1", bairro="Centro", municipio="Cidade",
        cep="12345-678", certificado="YQ==", senha="secret",
    )
    with TestClient(app) as client:
        malformed = client.post(path + "/connect", json={**form, "certificado": "private!"})
        assert malformed.status_code == 422
        assert "private!" not in malformed.text and "secret" not in malformed.text
        assert client.post(path + "/connect?tenant_id=2", json=form).status_code == 403
        assert client.post(path + "/connect", json=form).json() == {"connected": True}
        assert client.post(path + "/connect", json=form).status_code == 200
        create.assert_called_once()
        assert create.call_args.args[1] == "master"
        payload = create.call_args.args[2]
        assert payload["cnpj"] == profile["cnpj"] and payload["certificado_especifico"] is True
        assert client.put("/api/admin/store/fiscal", json={**profile, "legal_name": "Outro"}).status_code == 409

        order = {"order_id": 7, "products": {"2": {
            "codigo_ncm": "19059090", "cfop": "5102", "icms_origem": "0",
            "icms_situacao_tributaria": "102", "pis_situacao_tributaria": "07",
            "cofins_situacao_tributaria": "07", "unidade_comercial": "UN",
        }}}
        assert client.post(path + "/test", json=order).json() == {"ref": "FZtestT1O7", "status": "autorizado"}
        token.assert_called_once_with("http", "master", 42, profile["cnpj"])
        assert emit.call_args.args[1] == "homologation"
        user.tenant_id = 2
        assert client.get(path).json() == {"available": True, "connected": False}
        assert client.post(path + "/test", json=order).status_code == 409
        user.role = "operator"
        assert client.post(path + "/connect", json=form).status_code == 403
    engine.dispose()


def test_focus_company_lookup_requires_matching_id_and_cnpj_and_does_not_overwrite():
    import httpx
    import pytest

    from app.services.focus_companies import CompanyAlreadyRegistered, create_company, get_homologation_token

    cnpj = "12345678000195"
    status = {"id": 42, "cnpj": cnpj, "token_homologacao": "homologation"}

    def lookup(request):
        assert request.method == "GET"
        assert str(request.url) == f"https://api.focusnfe.com.br/v2/empresas?cnpj={cnpj}"
        assert request.headers["authorization"] == "Basic bWFzdGVyOg=="
        return httpx.Response(200, json=[status])

    with httpx.Client(transport=httpx.MockTransport(lookup)) as client:
        with pytest.raises(CompanyAlreadyRegistered):
            create_company(client, "master", {"cnpj": cnpj})
        assert get_homologation_token(client, "master", 42, cnpj) == "homologation"
        with pytest.raises(ValueError, match="emitente vinculado"):
            get_homologation_token(client, "master", 99, cnpj)
