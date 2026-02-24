from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.sql import nullslast

from app.core.database import get_db
from app.deps import get_request_tenant_id, require_role
from app.models.admin_user import AdminUser
from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.services.r2_storage import upload_file

router = APIRouter(prefix="/api/admin/menu", tags=["admin-menu"])
legacy_router = APIRouter(prefix="/api", tags=["admin-menu-legacy"])

class MenuCategoryOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    sort_order: int
    active: bool
    created_at: Optional[str] = None


class MenuCategoryCreate(BaseModel):
    tenant_id: int
    name: str = Field(..., min_length=1)
    sort_order: int = 0
    active: bool = True


class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class MenuItemOut(BaseModel):
    id: int
    tenant_id: int
    category_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price_cents: int
    image_url: Optional[str] = None
    active: bool
    created_at: Optional[str] = None


def _category_to_dict(category: MenuCategory) -> dict:
    return {
        "id": category.id,
        "tenant_id": category.tenant_id,
        "name": category.name,
        "sort_order": category.sort_order,
        "active": category.active,
        "created_at": category.created_at.isoformat() if category.created_at else None,
    }


def _resolve_base_url(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")

    if forwarded_host:
        scheme = forwarded_proto or request.url.scheme
        return f"{scheme}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


def _resolve_image_url(base_url: str, image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url
    if image_url.startswith("/"):
        return f"{base_url}{image_url}"
    return f"{base_url}/{image_url}"


def _menu_item_to_dict(item: MenuItem, base_url: str) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "category_id": item.category_id,
        "name": item.name,
        "description": item.description,
        "price_cents": item.price_cents,
        "image_url": _resolve_image_url(base_url, item.image_url),
        "active": item.active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def _save_upload(upload: UploadFile, tenant_id: int) -> str:
    return upload_file(
        file=upload,
        tenant_id=str(tenant_id),
        category="items",
    )


def _validate_category_id(db: Session, tenant_id: int, category_id: Optional[int]) -> None:
    if category_id is None:
        return
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant_id, MenuCategory.id == category_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=400, detail="Categoria inválida para o tenant")


def _list_categories(db: Session, tenant_id: int) -> list[dict]:
    categories = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant_id)
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.name.asc())
        .all()
    )
    return [_category_to_dict(category) for category in categories]


def _list_items(db: Session, tenant_id: int, base_url: str, category_id: Optional[int]) -> list[dict]:
    query = db.query(MenuItem).filter(MenuItem.tenant_id == tenant_id)
    if category_id is not None:
        query = query.filter(MenuItem.category_id == category_id)
    items = query.order_by(nullslast(MenuItem.category_id), MenuItem.name.asc()).all()
    return [_menu_item_to_dict(item, base_url) for item in items]


@router.get("/categories", response_model=List[MenuCategoryOut])
def list_categories(
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    return _list_categories(db, tenant_id)


@legacy_router.get("/categories", response_model=List[MenuCategoryOut])
def list_categories_legacy(
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    return _list_categories(db, tenant_id)


@router.post("/categories", response_model=MenuCategoryOut)
def create_category(
    payload: MenuCategoryCreate,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin"])),
):
    if int(user.tenant_id) != int(payload.tenant_id):
        raise HTTPException(status_code=403, detail="Tenant não autorizado")

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


@router.put("/categories/{category_id}", response_model=MenuCategoryOut)
def update_category(
    category_id: int,
    payload: MenuCategoryUpdate,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == category_id, MenuCategory.tenant_id == tenant_id)
        .first()
    )
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


@router.delete("/categories/{category_id}", response_model=MenuCategoryOut)
def delete_category(
    category_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.id == category_id, MenuCategory.tenant_id == tenant_id)
        .first()
    )
    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")

    category.active = False
    db.commit()
    db.refresh(category)
    return _category_to_dict(category)


@router.get("/items", response_model=List[MenuItemOut])
def list_items(
    request: Request,
    tenant_id: int = Depends(get_request_tenant_id),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    base_url = _resolve_base_url(request)
    return _list_items(db, tenant_id, base_url, category_id)


@legacy_router.get("/items", response_model=List[MenuItemOut])
def list_items_legacy(
    request: Request,
    tenant_id: int = Depends(get_request_tenant_id),
    category_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    base_url = _resolve_base_url(request)
    return _list_items(db, tenant_id, base_url, category_id)


@router.post("/items", response_model=MenuItemOut)
def create_item(
    request: Request,
    tenant_id: int = Form(...),
    name: str = Form(...),
    price_cents: int = Form(...),
    description: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    active: bool = Form(True),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin"])),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=403, detail="Tenant não autorizado")
    _validate_category_id(db, tenant_id, category_id)

    image_url = _save_upload(image, tenant_id) if image else None
    item = MenuItem(
        tenant_id=tenant_id,
        name=name,
        description=description,
        price_cents=price_cents,
        category_id=category_id,
        active=active,
        image_url=image_url,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item, _resolve_base_url(request))


@router.put("/items/{item_id}", response_model=MenuItemOut)
def update_item(
    request: Request,
    item_id: int,
    tenant_id: int = Form(...),
    name: Optional[str] = Form(None),
    price_cents: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    active: Optional[bool] = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_role(["admin"])),
):
    if int(user.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=403, detail="Tenant não autorizado")
    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")

    if name is not None:
        item.name = name
    if description is not None:
        item.description = description
    if price_cents is not None:
        item.price_cents = price_cents
    if category_id is not None:
        _validate_category_id(db, tenant_id, category_id)
        item.category_id = category_id
    if active is not None:
        item.active = active
    if image is not None:
        item.image_url = _save_upload(image, tenant_id)

    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item, _resolve_base_url(request))


@router.delete("/items/{item_id}", response_model=MenuItemOut)
def delete_item(
    request: Request,
    item_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    db: Session = Depends(get_db),
    _user: AdminUser = Depends(require_role(["admin"])),
):
    item = (
        db.query(MenuItem)
        .filter(MenuItem.id == item_id, MenuItem.tenant_id == tenant_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do cardápio não encontrado")

    item.active = False
    db.commit()
    db.refresh(item)
    return _menu_item_to_dict(item, _resolve_base_url(request))
