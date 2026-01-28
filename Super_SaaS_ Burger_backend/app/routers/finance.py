from datetime import date, datetime, time
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.finance import CashMovement

router = APIRouter(prefix="/api/finance", tags=["finance"])


class CashMovementRead(BaseModel):
    id: int
    tenant_id: int
    type: str
    category: str
    description: str | None
    amount_cents: int
    reference_type: str | None
    reference_id: int | None
    occurred_at: datetime
    created_at: datetime


class CashSummaryRead(BaseModel):
    opening_balance_cents: int
    total_in_cents: int
    total_out_cents: int
    net_cents: int
    by_category: Dict[str, int]


def _parse_date(value: str) -> date:
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Data inválida") from exc


def _date_range(from_str: str, to_str: str) -> tuple[datetime, datetime]:
    start_date = _parse_date(from_str)
    end_date = _parse_date(to_str)
    start = datetime.combine(start_date, time.min)
    end = datetime.combine(end_date, time.max)
    return start, end


def _movement_to_dict(movement: CashMovement) -> dict:
    return {
        "id": movement.id,
        "tenant_id": movement.tenant_id,
        "type": movement.type,
        "category": movement.category,
        "description": movement.description,
        "amount_cents": movement.amount_cents,
        "reference_type": movement.reference_type,
        "reference_id": movement.reference_id,
        "occurred_at": movement.occurred_at,
        "created_at": movement.created_at,
    }


@router.get("/cash/summary", response_model=CashSummaryRead)
def cash_summary(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    start, end = _date_range(from_date, to_date)
    movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .all()
    )

    total_in_cents = 0
    total_out_cents = 0
    by_category: Dict[str, int] = {}

    for movement in movements:
        if movement.type == "in":
            total_in_cents += movement.amount_cents
            by_category[movement.category] = by_category.get(movement.category, 0) + movement.amount_cents
        else:
            total_out_cents += movement.amount_cents
            by_category[movement.category] = by_category.get(movement.category, 0) - movement.amount_cents

    net_cents = total_in_cents - total_out_cents

    return {
        "opening_balance_cents": 0,
        "total_in_cents": total_in_cents,
        "total_out_cents": total_out_cents,
        "net_cents": net_cents,
        "by_category": by_category,
    }


@router.get("/cash/movements", response_model=List[CashMovementRead])
def list_cash_movements(
    tenant_id: int = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    start, end = _date_range(from_date, to_date)
    movements = (
        db.query(CashMovement)
        .filter(
            CashMovement.tenant_id == tenant_id,
            CashMovement.occurred_at >= start,
            CashMovement.occurred_at <= end,
        )
        .order_by(CashMovement.occurred_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_movement_to_dict(movement) for movement in movements]
