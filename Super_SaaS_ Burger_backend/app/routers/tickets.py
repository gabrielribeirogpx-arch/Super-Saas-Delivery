from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.services.printing import render_ticket_pdf

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get(
    "/orders/{order_id}/ticket",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}}},
)
def get_ticket(
    order_id: int,
    db: Session = Depends(get_db),
    admin_user: AdminUser = Depends(require_admin_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if int(admin_user.tenant_id) != int(order.tenant_id):
        raise HTTPException(status_code=403, detail="Tenant não autorizado")

    output = BytesIO()
    render_ticket_pdf(order, output)
    filename = f"pedido_{order.id}_tenant_{order.tenant_id}.pdf"
    return Response(
        output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"', "Cache-Control": "private, no-store"},
    )
