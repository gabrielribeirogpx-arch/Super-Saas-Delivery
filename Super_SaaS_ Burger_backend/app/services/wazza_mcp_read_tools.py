"""Read-only MCP tools backed by authoritative Fomizero data."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.menu_category import MenuCategory
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.tenant import Tenant
from app.services.menu_search import search_menu_items
from app.services.wazza_mcp_customer_tools import CUSTOMER_TOOL_DEFINITIONS
from app.services.wazza_mcp_errors import McpToolError
from app.services.wazza_mcp_identity import VerifiedCustomerIdentity
from app.services.wazza_mcp_confirmation import (
    DraftConfirmArguments, confirmation_available, order_draft_confirm,
)
from app.services.wazza_mcp_order_drafts import DRAFT_TOOL_DEFINITIONS


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=50, ge=1, le=100)


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=5, ge=1, le=10)


class ItemArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: int = Field(gt=0)


McpReadToolError = McpToolError


def _money_cents(value: Decimal | float | int | None) -> int:
    return int(round(float(value or 0) * 100))


def _tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise McpReadToolError("restaurant_not_found", "Restaurante não encontrado.")
    return tenant


def restaurant_get_status(db: Session, tenant_id: int, _: EmptyArguments) -> dict[str, Any]:
    tenant = _tenant(db, tenant_id)
    accepting = bool(tenant.is_active and tenant.manual_open_status)
    return {
        "restaurant": {
            "name": tenant.business_name or tenant.name,
            "slug": tenant.slug,
            "accepting_orders": accepting,
            "estimated_prep_time": tenant.estimated_prep_time,
            "delivery_fee_cents": _money_cents(tenant.delivery_fee),
        }
    }


def menu_list_categories(db: Session, tenant_id: int, args: CategoryArguments) -> dict[str, Any]:
    _tenant(db, tenant_id)
    rows = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant_id, MenuCategory.active.is_(True))
        .order_by(MenuCategory.sort_order.asc(), MenuCategory.id.asc())
        .limit(args.limit)
        .all()
    )
    item_counts = dict(
        db.query(MenuItem.category_id, func.count(MenuItem.id))
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.active.is_(True), MenuItem.category_id.in_([row.id for row in rows]) if rows else False)
        .group_by(MenuItem.category_id)
        .all()
    )
    return {
        "categories": [
            {"id": row.id, "name": row.name, "sort_order": row.sort_order, "active_items": int(item_counts.get(row.id, 0))}
            for row in rows
        ]
    }


def _item_data(item: MenuItem, category_name: str | None = None, score: float | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": item.id,
        "category_id": item.category_id,
        "category_name": category_name,
        "name": item.name,
        "description": item.description,
        "price_cents": int(item.price_cents),
        "available": bool(item.active),
    }
    if score is not None:
        data["match_score"] = round(float(score), 4)
    return data


def menu_search_items(db: Session, tenant_id: int, args: SearchArguments) -> dict[str, Any]:
    _tenant(db, tenant_id)
    matches = search_menu_items(db, tenant_id, args.query.strip(), limit=args.limit)
    category_ids = {item.category_id for item, _score in matches if item.category_id is not None}
    categories = {
        row.id: row.name
        for row in db.query(MenuCategory).filter(MenuCategory.tenant_id == tenant_id, MenuCategory.id.in_(category_ids) if category_ids else False).all()
    }
    return {"items": [_item_data(item, categories.get(item.category_id), score) for item, score in matches]}


def menu_get_item(db: Session, tenant_id: int, args: ItemArguments) -> dict[str, Any]:
    _tenant(db, tenant_id)
    item = (
        db.query(MenuItem)
        .filter(MenuItem.tenant_id == tenant_id, MenuItem.id == args.item_id, MenuItem.active.is_(True))
        .first()
    )
    if item is None:
        raise McpReadToolError("item_not_found", "Item não encontrado ou indisponível.")
    category = (
        db.query(MenuCategory)
        .filter(MenuCategory.tenant_id == tenant_id, MenuCategory.id == item.category_id, MenuCategory.active.is_(True))
        .first()
        if item.category_id is not None
        else None
    )
    groups = (
        db.query(ModifierGroup)
        .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.product_id == item.id, ModifierGroup.active.is_(True))
        .order_by(ModifierGroup.order_index.asc(), ModifierGroup.id.asc())
        .all()
    )
    group_ids = [group.id for group in groups]
    options = (
        db.query(ModifierOption)
        .filter(ModifierOption.group_id.in_(group_ids), ModifierOption.is_active.is_(True))
        .order_by(ModifierOption.order_index.asc(), ModifierOption.id.asc())
        .all()
        if group_ids
        else []
    )
    options_by_group: dict[int, list[dict[str, Any]]] = {group_id: [] for group_id in group_ids}
    for option in options:
        options_by_group[option.group_id].append(
            {
                "id": option.id,
                "name": option.name,
                "description": option.description,
                "price_delta_cents": _money_cents(option.price_delta),
                "is_default": bool(option.is_default),
            }
        )
    data = _item_data(item, category.name if category else None)
    data["modifier_groups"] = [
        {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "required": bool(group.required),
            "min_selection": int(group.min_selection or 0),
            "max_selection": int(group.max_selection or 1),
            "options": options_by_group[group.id],
        }
        for group in groups
    ]
    return {"item": data}


TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "restaurant_get_status": {
        "title": "Consultar status do restaurante",
        "description": "Retorna se o restaurante está aceitando pedidos, prazo estimado e taxa de entrega.",
        "scope": "menu:read",
        "arguments_model": EmptyArguments,
        "handler": restaurant_get_status,
    },
    "menu_list_categories": {
        "title": "Listar categorias do cardápio",
        "description": "Lista categorias ativas e a quantidade de itens disponíveis em cada uma.",
        "scope": "menu:read",
        "arguments_model": CategoryArguments,
        "handler": menu_list_categories,
    },
    "menu_search_items": {
        "title": "Pesquisar itens do cardápio",
        "description": "Pesquisa somente itens ativos do cardápio do restaurante autenticado.",
        "scope": "menu:read",
        "arguments_model": SearchArguments,
        "handler": menu_search_items,
    },
    "menu_get_item": {
        "title": "Consultar item e adicionais",
        "description": "Retorna preço atual, descrição e grupos de adicionais de um item disponível.",
        "scope": "menu:read",
        "arguments_model": ItemArguments,
        "handler": menu_get_item,
    },
    **CUSTOMER_TOOL_DEFINITIONS,
    **DRAFT_TOOL_DEFINITIONS,
    "order_draft_confirm": {
        "title": "Confirmar orçamento e criar pedido",
        "description": (
            "Use somente depois de o cliente confirmar explicitamente o orçamento exato. "
            "Envie o token desse orçamento e reutilize a chave em caso de timeout."
        ),
        "scope": "order:create",
        "arguments_model": DraftConfirmArguments,
        "handler": order_draft_confirm,
        "requires_customer": True,
        "risk": "destructive",
        "idempotent": True,
    },
}


def tool_is_available(name: str) -> bool:
    return name != "order_draft_confirm" or confirmation_available()


def public_tool_list(scopes: set[str]) -> list[dict[str, Any]]:
    tools = []
    for name, definition in TOOL_DEFINITIONS.items():
        if definition["scope"] not in scopes or not tool_is_available(name):
            continue
        model: type[BaseModel] = definition["arguments_model"]
        tools.append(
            {
                "name": name,
                "title": definition["title"],
                "description": definition["description"],
                "inputSchema": model.model_json_schema(),
                "annotations": {
                    "readOnlyHint": definition.get("risk", "read") == "read",
                    "destructiveHint": definition.get("risk") == "destructive",
                    "idempotentHint": definition.get("idempotent", True),
                },
            }
        )
    return tools


def execute_read_tool(
    db: Session,
    tenant_id: int,
    name: str,
    arguments: dict[str, Any],
    customer_identity: VerifiedCustomerIdentity | None = None,
) -> dict[str, Any]:
    definition = TOOL_DEFINITIONS.get(name)
    if definition is None or not tool_is_available(name):
        raise McpReadToolError("tool_not_found", "Ferramenta não encontrada.")
    model: type[BaseModel] = definition["arguments_model"]
    parsed = model.model_validate(arguments)
    if definition.get("requires_customer"):
        if customer_identity is None:
            raise McpReadToolError("customer_identity_required", "Identidade do cliente obrigatória.")
        return definition["handler"](db, tenant_id, parsed, customer_identity)
    handler: Callable[[Session, int, BaseModel], dict[str, Any]] = definition["handler"]
    return handler(db, tenant_id, parsed)
