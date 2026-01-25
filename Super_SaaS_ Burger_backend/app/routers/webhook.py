import os
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import META_WA_VERIFY_TOKEN
from app.core.database import get_db
from app.integrations.whatsapp import send_text
from app.models.processed_message import ProcessedMessage
from app.models.conversation import Conversation
from app.fsm.engine import iniciar_conversa, processar_mensagem
from app.services.orders import create_order_from_conversation

# ✅ versão nova do printing.py (PDF + tenta imprimir se tiver)
from app.services.printing import auto_print_if_possible, generate_ticket_pdf

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request):
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    if mode == "subscribe" and token == META_WA_VERIFY_TOKEN:
        return PlainTextResponse(challenge or "")

    raise HTTPException(status_code=403, detail="Verify token inválido")


def _extract_message(payload: dict) -> dict | None:
    entry = payload.get("entry") or []
    if not entry:
        return None

    changes = entry[0].get("changes") or []
    if not changes:
        return None

    value = changes[0].get("value") or {}

    metadata = value.get("metadata") or {}
    phone_number_id = metadata.get("phone_number_id")
    display_phone_number = metadata.get("display_phone_number")

    contacts = value.get("contacts") or []
    contact_name = None
    if contacts:
        contact_name = ((contacts[0].get("profile") or {}).get("name")) or None

    messages = value.get("messages") or []
    if not messages:
        return None

    msg = messages[0]
    message_id = msg.get("id")
    from_number = msg.get("from")
    msg_type = msg.get("type")

    if msg_type != "text":
        return None

    text = ((msg.get("text") or {}).get("body")) or ""

    if not message_id or not from_number:
        return None

    return {
        "message_id": message_id,
        "from_number": from_number,
        "text": text.strip(),
        "phone_number_id": phone_number_id,
        "display_phone_number": display_phone_number,
        "contact_name": contact_name,
    }


def _get_print_settings(tenant_id: int, db: Session) -> tuple[bool, str]:
    """
    1) Tenta pegar do BANCO (Tenant.auto_print / Tenant.printer_name)
    2) Fallback para .env (AUTO_PRINT / PRINTER_NAME)
    """
    auto_print_db = None
    printer_db = None

    try:
        from app.models.tenant import Tenant
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            auto_print_db = getattr(tenant, "auto_print", None)
            printer_db = getattr(tenant, "printer_name", None)
    except Exception:
        pass

    auto_print_env = (os.getenv("AUTO_PRINT", "0").strip() == "1")
    printer_env = (os.getenv("PRINTER_NAME", "").strip() or "")

    auto_print = auto_print_env if auto_print_db is None else bool(auto_print_db)
    printer = printer_env if not printer_db else str(printer_db).strip()

    return auto_print, printer


@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()

    extracted = _extract_message(payload)
    if not extracted:
        return {"status": "ignored"}

    message_id = extracted["message_id"]
    from_number = extracted["from_number"]
    text = extracted["text"]
    contact_name = extracted.get("contact_name")

    # 1) Anti-duplicidade
    if db.query(ProcessedMessage).filter_by(message_id=message_id).first():
        return {"status": "duplicate"}

    db.add(ProcessedMessage(message_id=message_id))
    db.commit()

    # 2) Tenant padrão nesta fase (depois troca por lookup do phone_number_id/waba)
    tenant_id = 1

    # 3) Carrega/cria conversa
    conversa = (
        db.query(Conversation)
        .filter_by(tenant_id=tenant_id, telefone=from_number)
        .first()
    )

    # 4) FSM decide resposta
    if not conversa:
        conversa = Conversation(tenant_id=tenant_id, telefone=from_number)
        resposta = iniciar_conversa(conversa, db, tenant_id)
        db.add(conversa)
        db.commit()

        try:
            await send_text(to=from_number, text=resposta)
        except Exception as e:
            print("ERRO AO ENVIAR WHATSAPP (start):", str(e))

        return {"status": "ok", "flow": "started"}

    resposta = processar_mensagem(conversa, text, db, tenant_id)
    db.commit()

    # 5) Se chegou em PEDIDO_CRIADO, cria pedido e gera PDF (e imprime se tiver)
    try:
        estado = getattr(conversa, "estado", "")
        last_order_id = getattr(conversa, "last_order_id", None)

        if estado == "PEDIDO_CRIADO" and not last_order_id:
            order = create_order_from_conversation(
                db,
                tenant_id,
                conversa,
                contact_name=contact_name
            )

            # marca que já criou pra não duplicar
            try:
                conversa.last_order_id = order.id
                db.commit()
            except Exception:
                pass

            # ✅ Config de impressão (db → env)
            auto_print, printer_name = _get_print_settings(tenant_id, db)

            # Empurra config pro printing.py (sem depender do usuário mexer em .env)
            # (printing.py lê AUTO_PRINT/PRINTER_NAME também)
            os.environ["AUTO_PRINT"] = "1" if auto_print else "0"
            if printer_name:
                os.environ["PRINTER_NAME"] = printer_name

            # ✅ sempre gera PDF + tenta imprimir se houver impressora
            pdf_path = generate_ticket_pdf(order, tenant_id)
            result = auto_print_if_possible(tenant_id, pdf_path)
            print("TICKET:", result, "PDF:", pdf_path)
    except Exception as e:
        print("ERRO AO SALVAR/GERAR ETIQUETA:", str(e))

    # 6) Envia resposta do FSM
    try:
        await send_text(to=from_number, text=resposta)
    except Exception as e:
        print("ERRO AO ENVIAR WHATSAPP (continued):", str(e))

    return {"status": "ok", "flow": "continued"}
