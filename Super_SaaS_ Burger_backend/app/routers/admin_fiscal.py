import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.fiscal_profile import FiscalProfile

router = APIRouter(prefix="/api/admin/store/fiscal", tags=["admin-fiscal"])
STATES = frozenset("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())


class FiscalProfileData(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)

    cnpj: str = Field(max_length=18)
    legal_name: str = Field(min_length=2, max_length=120)
    state_registration: str = Field(max_length=24)
    state_code: str = Field(min_length=2, max_length=2)
    tax_regime: Literal[1, 2, 3, 4]

    @field_validator("cnpj")
    @classmethod
    def validate_cnpj(cls, value: str) -> str:
        normalized = re.sub(r"[./-]", "", value.upper())
        if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized) or len(set(normalized)) == 1:
            raise ValueError("Informe um CNPJ válido.")
        stem = normalized[:12]
        for digit in normalized[12:]:
            total = sum(
                (ord(char) - 48) * (2 + index % 8)
                for index, char in enumerate(reversed(stem))
            )
            if int(digit) != (total * 10 % 11) % 10:
                raise ValueError("Informe um CNPJ válido.")
            stem += digit
        return normalized

    @field_validator("state_registration")
    @classmethod
    def normalize_state_registration(cls, value: str) -> str:
        normalized = re.sub(r"[. /-]", "", value.upper())
        if not re.fullmatch(r"[0-9]{2,14}|P[0-9]{2,13}", normalized):
            raise ValueError("Informe a inscrição estadual do estabelecimento.")
        return normalized

    @field_validator("state_code")
    @classmethod
    def validate_state_code(cls, value: str) -> str:
        if value.upper() not in STATES:
            raise ValueError("Selecione uma UF válida.")
        return value.upper()


@router.get("", response_model=FiscalProfileData | None)
def get_profile(
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    return db.get(FiscalProfile, user.tenant_id)


@router.put("", response_model=FiscalProfileData)
def save_profile(
    payload: FiscalProfileData,
    user: AdminUser = Depends(require_role(["admin", "owner"])),
    db: Session = Depends(get_db),
):
    values = payload.model_dump()
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(FiscalProfile).values(tenant_id=user.tenant_id, **values)
    result = db.execute(statement.on_conflict_do_update(
        index_elements=[FiscalProfile.tenant_id],
        set_=values,
        where=(
            FiscalProfile.focus_company_id.is_(None)
            | (
                (FiscalProfile.cnpj == payload.cnpj)
                & (FiscalProfile.state_code == payload.state_code)
                & (FiscalProfile.state_registration == payload.state_registration)
                & (FiscalProfile.tax_regime == payload.tax_regime)
                & (FiscalProfile.legal_name == payload.legal_name)
            )
        ),
    ))
    if not result.rowcount:
        raise HTTPException(409, "Para alterar os dados de um emitente configurado, fale com o suporte do Fomizero.")
    db.commit()
    return payload
