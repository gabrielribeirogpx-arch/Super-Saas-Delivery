from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.menu_category import MenuCategory

router = APIRouter(prefix="/api/menu/categories", tags=["menu-categories"])


class MenuCategoryOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    sort_order: int
    active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MenuCategoryCreate(BaseModel):
    tenant_id: int
    name: str = Field(..., min_length=1)
    sort_order: int = 0
    active: bool = True


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    sort_order: Optional[int] = None
    active: Optional[bool] = None


def _category_to_dict(category: MenuCategory) -> dict:
    return {
        "id": category.id,
        "tenant_id": category.tenant_id,
        "name": category.name,
        "sort_order": category.sort_order,
        "active": category.active,
        "created_at": category.created_at.isoformat() if category.created_at else None,
        "updated_at": category.updated_at.isoformat() if category.updated_at else None,
    }


@router.get("", response_model=List[MenuCategoryOut])
def list_categories(
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant_id)
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
        .all()
    )
    return [_category_to_dict(category) for category in categories]


@router.post("", response_model=MenuCategoryOut)
def create_category(
    payload: MenuCategoryCreate,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    category = MenuCategory(
        tenant_id=payload.tenant_id,
        name=payload.name,
        sort_order=payload.sort_order,
        active=payload.active,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


@router.put("/{category_id}", response_model=MenuCategoryOut)
def update_category(
    category_id: int,
    payload: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    category = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    if payload.name is not None:
        category.name = payload.name
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.active is not None:
        category.active = payload.active

    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


@router.delete("/{category_id}", response_model=MenuCategoryOut)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    category = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    category.active = False
    db.commit()
    db.refresh(category)
    return _category_to_dict(category)
