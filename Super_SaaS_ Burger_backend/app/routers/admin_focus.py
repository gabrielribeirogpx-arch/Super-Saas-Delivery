import base64
import binascii
import os
import re
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile
from app.services.focus_companies import CompanyAlreadyRegistered, create_company, get_homologation_token
from app.services.focus_nfce import FiscalProduct, prepare_payload, submit_or_consult

router = APIRouter(prefix="/api/admin/store/fiscal/focus", tags=["admin-fiscal"])
fiscal_admin = require_role(["admin", "owner"])


class FocusConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logradouro: str = Field(min_length=1, max_length=120)
    numero: str = Field(min_length=1, max_length=60)
    bairro: str = Field(min_length=1, max_length=80)
    municipio: str = Field(min_length=1, max_length=80)
    cep: str = Field(pattern=r"^[0-9]{5}-?[0-9]{3}$")
    certificado: SecretStr = Field(min_length=1, max_length=88000)
    senha: SecretStr = Field(max_length=256)
    csc: SecretStr | None = Field(default=None, min_length=1, max_length=128)
    id_csc: int | None = Field(default=None, ge=1, le=999999)


class FiscalTestOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int = Field(gt=0)
    products: dict[Annotated[int, Field(gt=0)], FiscalProduct] = Field(min_length=1, max_length=100)


def settings() -> tuple[str, str] | None:
    master = os.getenv("FOCUS_NFE_MASTER_TOKEN", "").strip()
    namespace = os.getenv("FOCUS_NFCE_PILOT_NAMESPACE", "")
    if master and re.fullmatch(r"[A-Za-z0-9]{1,20}", namespace):
        return master, namespace
    return None


def focus_settings() -> tuple[str, str]:
    config = settings()
    if not config:
        raise HTTPException(503, "A integração fiscal ainda não foi habilitada no servidor.")
    return config


@router.get("")
def connection_status(
    user: AdminUser = Depends(fiscal_admin), db: Session = Depends(get_db),
):
    profile = db.get(FiscalProfile, user.tenant_id)
    return {"available": settings() is not None, "connected": bool(profile and profile.focus_company_id)}


@router.post("/connect")
async def connect(
    request: Request,
    user: AdminUser = Depends(fiscal_admin),
    db: Session = Depends(get_db),
    config: tuple[str, str] = Depends(focus_settings),
):
    # Validate manually so request errors never echo the certificate, password or CSC.
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 96_000:
            raise HTTPException(413, "O arquivo do certificado é grande demais.")
        raw.extend(chunk)
    try:
        data = FocusConnection.model_validate_json(raw)
        certificate = data.certificado.get_secret_value()
        if not base64.b64decode(certificate, validate=True):
            raise ValueError
    except (ValidationError, ValueError, binascii.Error):
        raise HTTPException(422, "Confira os dados do endereço e do certificado.") from None

    if (data.csc is None) != (data.id_csc is None):
        raise HTTPException(422, "Informe o CSC e seu identificador juntos.")
    return await run_in_threadpool(provision, db, user.tenant_id, data, config[0])


def provision(db: Session, tenant_id: int, data: FocusConnection, master: str):
    profile = db.query(FiscalProfile).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    if not profile:
        raise HTTPException(409, "Salve os dados fiscais da loja primeiro.")
    if profile.focus_company_id:
        return {"connected": True}
    if not re.fullmatch(r"[0-9]{14}", profile.cnpj):
        raise HTTPException(422, "A consulta de empresas da Focus exige CNPJ numérico neste piloto.")
    payload = {
        **data.model_dump(include={"logradouro", "numero", "bairro", "municipio"}),
        "cep": int(data.cep.replace("-", "")),
        "cnpj": profile.cnpj,
        "nome": profile.legal_name,
        "inscricao_estadual": profile.state_registration,
        "uf": profile.state_code,
        "regime_tributario": profile.tax_regime,
        "habilita_nfce": True,
        "certificado_especifico": True,
        "arquivo_certificado_base64": data.certificado.get_secret_value(),
        "senha_certificado": data.senha.get_secret_value(),
    }
    if data.csc is not None:
        payload["csc_nfce_homologacao"] = data.csc.get_secret_value()
        payload["id_token_nfce_homologacao"] = data.id_csc
    try:
        with httpx.Client(timeout=25, trust_env=False) as client:
            profile.focus_company_id = create_company(client, master, payload)
        db.commit()
    except CompanyAlreadyRegistered:
        raise HTTPException(409, "Este CNPJ já está cadastrado na Focus. Solicite suporte para vincular o cadastro existente.") from None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 409, 422}:
            raise HTTPException(
                422, "A Focus recusou o cadastro. Confira o certificado, os dados fiscais e se o CNPJ já existe na Focus.",
            ) from None
        raise HTTPException(502, "A Focus não pôde cadastrar o emitente.") from None
    except (httpx.RequestError, ValueError, IntegrityError):
        raise HTTPException(502, "Não foi possível confirmar o cadastro na Focus. Verifique o emitente com o suporte.") from None
    return {"connected": True}


@router.post("/test")
def emit_test(
    data: FiscalTestOrder,
    user: AdminUser = Depends(fiscal_admin),
    db: Session = Depends(get_db),
    config: tuple[str, str] = Depends(focus_settings),
):
    profile = db.get(FiscalProfile, user.tenant_id)
    if not profile or not profile.focus_company_id:
        raise HTTPException(409, "Conecte o emitente primeiro.")
    master, namespace = config
    ref = f"FZ{namespace}T{user.tenant_id}O{data.order_id}"
    try:
        payload = prepare_payload(db, user.tenant_id, data.order_id, data.products)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    try:
        with httpx.Client(timeout=25, trust_env=False) as client:
            token = get_homologation_token(client, master, profile.focus_company_id, profile.cnpj)
            result = submit_or_consult(client, token, ref, payload)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            502, f"A Focus não retornou um resultado confirmado. Tente consultar novamente pelo mesmo pedido ({ref}).",
        ) from None
    return {"ref": ref, **{
        field: result[field]
        for field in ("status", "status_sefaz", "mensagem_sefaz", "chave_nfe")
        if isinstance(result.get(field), str)
    }}
