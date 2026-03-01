from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.schemas.product_configuration import ModifierGroupResponse
from app.services.product_configuration import list_modifier_groups_for_product

router = APIRouter(prefix="/api/admin", tags=["admin-product-configuration"])


class ModifierGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    required: bool = False
    min_selection: int = 0
    max_selection: int = 1
    order_index: int = 0


class ModifierGroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    required: Optional[bool] = None
    min_selection: Optional[int] = None
    max_selection: Optional[int] = None
    order_index: Optional[int] = None
    active: Optional[bool] = None


class ModifierOptionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price_delta: Decimal = Decimal("0")
    is_default: bool = False
    is_active: bool = True
    order_index: int = 0


class ModifierOptionUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price_delta: Optional[Decimal] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None


def _get_product_or_404(db: Session, tenant_id: int, product_id: int) -> MenuItem:
    product = db.query(MenuItem).filter(MenuItem.id == product_id, MenuItem.tenant_id == tenant_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    return product


def _get_group_or_404(db: Session, tenant_id: int, group_id: int) -> ModifierGroup:
    group = db.query(ModifierGroup).filter(ModifierGroup.id == group_id, ModifierGroup.tenant_id == tenant_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return group


def _validate_group_bounds(min_selection: int, max_selection: int) -> None:
    if min_selection < 0 or max_selection < 0:
        raise HTTPException(status_code=400, detail="min_selection/max_selection inválidos")
    if min_selection > max_selection:
        raise HTTPException(status_code=400, detail="min_selection não pode ser maior que max_selection")


@router.post("/products/{product_id}/modifier-groups", response_model=ModifierGroupResponse)
def create_modifier_group(
    product_id: int,
    payload: ModifierGroupCreateRequest,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    _get_product_or_404(db, tenant_id, product_id)
    _validate_group_bounds(payload.min_selection, payload.max_selection)

    group = ModifierGroup(
        tenant_id=tenant_id,
        product_id=product_id,
        name=payload.name,
        description=payload.description,
        required=payload.required,
        min_selection=payload.min_selection,
        max_selection=payload.max_selection,
        order_index=payload.order_index,
        active=True,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return list_modifier_groups_for_product(
        db, tenant_id=tenant_id, product_id=product_id, only_active_options=False
    )[-1]


@router.patch("/modifier-groups/{group_id}", response_model=ModifierGroupResponse)
def update_modifier_group(
    group_id: int,
    payload: ModifierGroupUpdateRequest,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    group = _get_group_or_404(db, tenant_id, group_id)
    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    if payload.required is not None:
        group.required = payload.required
    if payload.min_selection is not None:
        group.min_selection = payload.min_selection
    if payload.max_selection is not None:
        group.max_selection = payload.max_selection
    _validate_group_bounds(int(group.min_selection or 0), int(group.max_selection or 1))
    if payload.order_index is not None:
        group.order_index = payload.order_index
    if payload.active is not None:
        group.active = payload.active

    db.commit()
    data = list_modifier_groups_for_product(
        db, tenant_id=tenant_id, product_id=int(group.product_id or 0), only_active_options=False
    )
    for item in data:
        if item["id"] == group.id:
            return item
    raise HTTPException(status_code=404, detail="Grupo não encontrado")


@router.delete("/modifier-groups/{group_id}")
def delete_modifier_group(
    group_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    group = _get_group_or_404(db, tenant_id, group_id)
    group.active = False
    db.query(ModifierOption).filter(ModifierOption.group_id == group.id).update(
        {ModifierOption.is_active: False},
        synchronize_session=False,
    )
    db.commit()
    return {"ok": True}


@router.post("/modifier-groups/{group_id}/options")
def create_modifier_option(
    group_id: int,
    payload: ModifierOptionCreateRequest,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    _get_group_or_404(db, tenant_id, group_id)
    option = ModifierOption(group_id=group_id, **payload.model_dump())
    db.add(option)
    db.commit()
    db.refresh(option)
    return {"id": option.id}


@router.patch("/modifier-options/{option_id}")
def update_modifier_option(
    option_id: int,
    payload: ModifierOptionUpdateRequest,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    option = db.query(ModifierOption).filter(ModifierOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Opção não encontrada")
    _get_group_or_404(db, tenant_id, int(option.group_id))

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(option, key, value)
    db.commit()
    return {"ok": True}


@router.delete("/modifier-options/{option_id}")
def delete_modifier_option(
    option_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "owner", "operator"])),
):
    option = db.query(ModifierOption).filter(ModifierOption.id == option_id).first()
    if not option:
        raise HTTPException(status_code=404, detail="Opção não encontrada")
    _get_group_or_404(db, tenant_id, int(option.group_id))
    option.is_active = False
    db.commit()
    return {"ok": True}
