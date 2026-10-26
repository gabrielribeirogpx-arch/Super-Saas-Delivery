from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.order import Order

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/orders/{order_id}/ticket")
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

    path = Path("tickets") / f"tenant_{order.tenant_id}" / f"pedido_{order.id}_tenant_{order.tenant_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)
