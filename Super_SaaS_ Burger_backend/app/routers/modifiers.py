from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.admin_user import AdminUser
from app.models.menu_item import MenuItem
from app.models.menu_item_modifier_group import MenuItemModifierGroup
from app.models.modifier import Modifier
from app.models.modifier_group import ModifierGroup
from app.services.admin_audit import log_admin_action

router = APIRouter(prefix="/api/modifiers", tags=["modifiers"])


class ModifierGroupOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    active: bool
    created_at: Optional[str] = None


class ModifierGroupCreate(BaseModel):
    tenant_id: int
    name: str = Field(..., min_length=1)
    active: bool = True


class ModifierOut(BaseModel):
    id: int
    tenant_id: int
    group_id: int
    name: str
    price_cents: int
    created_at: Optional[str] = None


class ModifierCreate(BaseModel):
    name: str = Field(..., min_length=1)
    price_cents: int = Field(..., ge=0)


class MenuItemGroupAssign(BaseModel):
    group_ids: List[int] = Field(default_factory=list)


def _group_to_dict(group: ModifierGroup) -> dict:
    return {
        "id": group.id,
        "tenant_id": group.tenant_id,
        "name": group.name,
        "active": group.active,
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


def _modifier_to_dict(modifier: Modifier) -> dict:
    return {
        "id": modifier.id,
        "tenant_id": modifier.tenant_id,
        "group_id": modifier.group_id,
        "name": modifier.name,
        "price_cents": modifier.price_cents,
        "created_at": modifier.created_at.isoformat() if modifier.created_at else None,
    }


@router.get("/groups/{tenant_id}", response_model=List[ModifierGroupOut])
def list_groups(
    tenant_id: int,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    groups = (
        db.query(ModifierGroup)
        .filter(ModifierGroup.tenant_id == tenant_id)
        .order_by(ModifierGroup.name.asc())
        .all()
    )
    return [_group_to_dict(group) for group in groups]


@router.post("/groups/{tenant_id}", response_model=ModifierGroupOut)
def create_group(
    tenant_id: int,
    payload: ModifierGroupCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    if payload.tenant_id != tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id inconsistente")
    group = ModifierGroup(
        tenant_id=tenant_id,
        name=payload.name,
        active=payload.active,
    )
    db.add(group)
    db.flush()
    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="create_modifier_group",
        entity_type="modifier_group",
        entity_id=group.id,
    )
    db.commit()
    db.refresh(group)
    return _group_to_dict(group)


@router.get("/groups/{tenant_id}/{group_id}/modifiers", response_model=List[ModifierOut])
def list_modifiers(
    tenant_id: int,
    group_id: int,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    group = (
        db.query(ModifierGroup)
        .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    modifiers = (
        db.query(Modifier)
        .filter(Modifier.tenant_id == tenant_id, Modifier.group_id == group_id)
        .order_by(Modifier.name.asc())
        .all()
    )
    return [_modifier_to_dict(modifier) for modifier in modifiers]


@router.post("/groups/{tenant_id}/{group_id}/modifiers", response_model=ModifierOut)
def create_modifier(
    tenant_id: int,
    group_id: int,
    payload: ModifierCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    group = (
        db.query(ModifierGroup)
        .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    modifier = Modifier(
        tenant_id=tenant_id,
        group_id=group_id,
        name=payload.name,
        price_cents=payload.price_cents,
    )
    db.add(modifier)
    db.flush()
    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="create_modifier",
        entity_type="modifier",
        entity_id=modifier.id,
    )
    db.commit()
    db.refresh(modifier)
    return _modifier_to_dict(modifier)


@router.post("/menu/{tenant_id}/{item_id}/groups")
def assign_groups_to_item(
    tenant_id: int,
    item_id: int,
    payload: MenuItemGroupAssign,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")

    group_ids = list({gid for gid in payload.group_ids if gid is not None})
    if group_ids:
        valid_groups = (
            db.query(ModifierGroup.id)
            .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.id.in_(group_ids))
            .all()
        )
        valid_group_ids = {gid for (gid,) in valid_groups}
        invalid = [gid for gid in group_ids if gid not in valid_group_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Grupos inválidos para o tenant: {invalid}",
            )
    else:
        valid_group_ids = set()

    db.query(MenuItemModifierGroup).filter(
        MenuItemModifierGroup.tenant_id == tenant_id,
        MenuItemModifierGroup.menu_item_id == item_id,
    ).delete()

    for gid in valid_group_ids:
        db.add(
            MenuItemModifierGroup(
                tenant_id=tenant_id,
                menu_item_id=item_id,
                modifier_group_id=gid,
            )
        )

    db.commit()
    return {"ok": True, "menu_item_id": item_id, "group_ids": list(valid_group_ids)}


@router.get("/menu/{tenant_id}/{item_id}/groups")
def list_groups_for_item(
    tenant_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin", "operator"])),
):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")

    groups = (
        db.query(MenuItemModifierGroup.modifier_group_id)
        .filter(
            MenuItemModifierGroup.tenant_id == tenant_id,
            MenuItemModifierGroup.menu_item_id == item_id,
        )
        .all()
    )
    group_ids = [gid for (gid,) in groups]
    return {"ok": True, "menu_item_id": item_id, "group_ids": group_ids}
