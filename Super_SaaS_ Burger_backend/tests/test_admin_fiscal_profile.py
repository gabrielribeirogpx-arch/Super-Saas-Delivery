from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile
from app.models.tenant import Tenant
from app.routers.admin_fiscal import router


def test_fiscal_profile_validates_and_is_scoped_to_the_admin_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fiscal.db'}")
    Tenant.__table__.create(engine)
    FiscalProfile.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([Tenant(id=1, slug="one"), Tenant(id=2, slug="two")])
        db.commit()

    def open_session():
        with Session(engine) as db:
            yield db

    user = AdminUser(id=1, tenant_id=1, role="owner")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = open_session
    app.dependency_overrides[require_admin_user] = lambda: user
    path = "/api/admin/store/fiscal"
    profile = {
        "cnpj": "12.345.678/0001-95",
        "legal_name": "Restaurante de teste",
        "state_registration": "123.456.789.000",
        "state_code": "sp",
        "tax_regime": 1,
    }
    with TestClient(app) as client:
        assert client.get(path).json() is None
        assert client.put(path, json={**profile, "cnpj": "12.345.678/0001-96"}).status_code == 422
        assert client.put(path, json={**profile, "tenant_id": 2}).status_code == 422
        assert client.put(path, params={"tenant_id": 2}, json=profile).status_code == 403
        saved = client.put(path, json=profile)
        assert saved.status_code == 200
        assert saved.json() == {
            **profile, "cnpj": "12345678000195", "state_registration": "123456789000", "state_code": "SP",
        }
        assert client.get(path).json() == saved.json()
        changed = client.put(path, json={**profile, "cnpj": "12.ABC.345/01DE-35"})
        assert changed.status_code == 200
        assert client.get(path).json()["cnpj"] == "12ABC34501DE35"
        user.tenant_id = 2
        assert client.get(path).json() is None
        user.role = "operator"
        assert client.get(path).status_code == 403
        assert client.put(path, json=profile).status_code == 403
    engine.dispose()
