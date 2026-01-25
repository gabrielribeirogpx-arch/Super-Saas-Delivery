from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/orders/{order_id}/ticket")
def get_ticket(order_id: int):
    path = Path("tickets") / f"pedido_{order_id}.pdf"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Etiqueta não encontrada")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)
