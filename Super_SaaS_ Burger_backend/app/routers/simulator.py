from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.conversation import Conversation
from app.fsm.engine import iniciar_conversa, processar_mensagem

router = APIRouter(prefix="/simulator")

@router.post("/mensagem")
def simular(tenant_id: int, telefone: str, texto: str, db: Session = Depends(get_db)):
    conversa = (
        db.query(Conversation)
        .filter_by(tenant_id=tenant_id, telefone=telefone)
        .first()
    )

    if not conversa:
        conversa = Conversation(tenant_id=tenant_id, telefone=telefone)
        resposta = iniciar_conversa(conversa, db, tenant_id)
        db.add(conversa)
        db.commit()
        return {
            "estado": conversa.estado,
            "resposta": resposta
        }

    resposta = processar_mensagem(conversa, texto, db, tenant_id)
    db.commit()

    return {
        "estado": conversa.estado,
        "resposta": resposta
    }
