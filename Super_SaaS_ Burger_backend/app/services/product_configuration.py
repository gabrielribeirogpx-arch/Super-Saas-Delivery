from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption


def list_modifier_groups_for_product(
    db: Session,
    *,
    tenant_id: int,
    product_id: int,
    only_active_options: bool,
) -> list[dict]:
    groups = (
        db.query(ModifierGroup)
        .filter(
            ModifierGroup.tenant_id == tenant_id,
            ModifierGroup.product_id == product_id,
            ModifierGroup.active.is_(True),
        )
        .order_by(ModifierGroup.order_index.asc(), ModifierGroup.id.asc())
        .all()
    )
    if not groups:
        return []

    group_ids = [group.id for group in groups]
    options_query = db.query(ModifierOption).filter(ModifierOption.group_id.in_(group_ids))
    if only_active_options:
        options_query = options_query.filter(ModifierOption.is_active.is_(True))
    options = options_query.order_by(ModifierOption.order_index.asc(), ModifierOption.id.asc()).all()

    options_by_group: dict[int, list[ModifierOption]] = {}
    for option in options:
        options_by_group.setdefault(option.group_id, []).append(option)

    payload: list[dict] = []
    for group in groups:
        payload.append(
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "required": bool(group.required),
                "min_selection": int(group.min_selection or 0),
                "max_selection": int(group.max_selection or 1),
                "options": [
                    {
                        "id": option.id,
                        "name": option.name,
                        "description": option.description,
                        "price_delta": Decimal(option.price_delta or 0),
                        "is_default": bool(option.is_default),
                        "is_active": bool(option.is_active),
                        "order_index": int(option.order_index or 0),
                    }
                    for option in options_by_group.get(group.id, [])
                ],
            }
        )
    return payload
