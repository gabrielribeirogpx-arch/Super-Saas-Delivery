import logging
import os

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import IS_DEV, META_WA_VERIFY_TOKEN
from app.core.database import get_db
from app.ai.service import run_assistant
from app.models.ai_config import AIConfig
from app.models.conversation import Conversation
from app.models.processed_message import ProcessedMessage
from app.models.whatsapp_config import WhatsAppConfig
from app.fsm.engine import iniciar_conversa, processar_mensagem
from app.services.menu_search import normalize
from app.services.orders import create_order_from_conversation
from app.services.printing import auto_print_if_possible, get_print_settings
from app.whatsapp.cloud_provider import parse_cloud_webhook
from app.whatsapp.service import WhatsAppService

router = APIRouter()
logger = logging.getLogger(__name__)


def _coerce_to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0

    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off", ""}:
        return False

    return default


@router.get("/webhook")
async def verify_webhook(request: Request):
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    if mode == "subscribe" and token == META_WA_VERIFY_TOKEN:
        return PlainTextResponse(challenge or "")

    raise HTTPException(status_code=403, detail="Verify token inválido")


def _resolve_whatsapp_config(
    db: Session,
    *,
    tenant_id: int | None,
    phone_number_id: str | None,
    waba_id: str | None,
) -> tuple[WhatsAppConfig | None, str]:
    """
    Resolve o tenant para o handshake do webhook:
    - prioridade: tenant_id (query param)
    - fallback: phone_number_id ou waba_id (query params)
    - em DEV, se nada foi enviado, tenta o tenant 1 por padrão
    """
    if tenant_id is not None:
        config = db.query(WhatsAppConfig).filter(WhatsAppConfig.tenant_id == tenant_id).first()
        return config, f"tenant_id={tenant_id}"

    if phone_number_id:
        config = (
            db.query(WhatsAppConfig)
            .filter(WhatsAppConfig.phone_number_id == phone_number_id)
            .first()
        )
        return config, f"phone_number_id={phone_number_id}"

    if waba_id:
        config = db.query(WhatsAppConfig).filter(WhatsAppConfig.waba_id == waba_id).first()
        return config, f"waba_id={waba_id}"

    if IS_DEV:
        config = db.query(WhatsAppConfig).filter(WhatsAppConfig.tenant_id == 1).first()
        return config, "dev_default_tenant=1"

    return None, "unresolved"


@router.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    request: Request,
    mode: str | None = Query(None, alias="hub.mode"),
    verify_token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
    tenant_id: int | None = Query(None),
    phone_number_id: str | None = Query(None),
    waba_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    config, tenant_source = _resolve_whatsapp_config(
        db,
        tenant_id=tenant_id,
        phone_number_id=phone_number_id,
        waba_id=waba_id,
    )
    expected_token = (config.verify_token or "").strip() if config else ""
    token_source = "tenant_config" if expected_token else "env:WHATSAPP_VERIFY_TOKEN"
    if not expected_token:
        expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()

    logger.info(
        "WhatsApp webhook verify: path=%s mode=%s token_present=%s tenant_source=%s token_source=%s",
        request.url.path,
        mode,
        bool(verify_token),
        tenant_source,
        token_source,
    )

    if mode != "subscribe":
        logger.warning("WhatsApp webhook verify: modo inválido: %s", mode)
        raise HTTPException(status_code=400, detail="hub.mode inválido (esperado subscribe).")

    if not verify_token:
        logger.warning("WhatsApp webhook verify: verify_token ausente.")
        raise HTTPException(status_code=403, detail="Verify token ausente.")

    if not expected_token or verify_token != expected_token:
        logger.warning(
            "WhatsApp webhook verify: token inválido (tenant_source=%s token_source=%s).",
            tenant_source,
            token_source,
        )
        raise HTTPException(
            status_code=403,
            detail="Verify token inválido para o webhook do WhatsApp.",
        )

    return PlainTextResponse(challenge or "")


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

    auto_print_env = _coerce_to_bool(os.getenv("AUTO_PRINT", "0"), default=False)
    printer_env = (os.getenv("PRINTER_NAME", "").strip() or "")

    auto_print = auto_print_env if auto_print_db is None else _coerce_to_bool(auto_print_db)
    printer = printer_env if not printer_db else str(printer_db).strip()

    return auto_print, printer


def _verify_tenant_token(db: Session, tenant_id: int, token: str | None) -> bool:
    if not token:
        return False
    config = db.query(WhatsAppConfig).filter(WhatsAppConfig.tenant_id == tenant_id).first()
    if config and config.verify_token:
        return token == config.verify_token
    if tenant_id == 1 and META_WA_VERIFY_TOKEN:
        return token == META_WA_VERIFY_TOKEN
    return False


def _handle_inbound_message(
    db: Session,
    *,
    tenant_id: int,
    message_id: str,
    from_number: str,
    text: str,
    message_type: str = "text",
    contact_name: str | None = None,
    phone_number_id: str | None = None,
):
    logger.info(
        "WhatsApp recebido: tenant=%s from=%s message_id=%s text='%s'",
        tenant_id,
        from_number,
        message_id,
        text,
    )
    logger.info("WhatsApp normalizado: from=%s text='%s'", from_number, normalize(text))

    if db.query(ProcessedMessage).filter_by(message_id=message_id).first():
        return {"status": "duplicate"}

    db.add(ProcessedMessage(message_id=message_id))
    db.commit()

    service = WhatsAppService()
    service.log_inbound(
        db,
        tenant_id=tenant_id,
        from_phone=from_number,
        to_phone=phone_number_id,
        message_type=message_type,
        payload={"text": text, "contact_name": contact_name},
        provider_message_id=message_id,
    )

    ai_config = db.query(AIConfig).filter(AIConfig.tenant_id == tenant_id).first()
    if ai_config and ai_config.enabled:
        assistant_json, final_text = run_assistant(tenant_id, from_number, text, db)
        try:
            service.send_text(db, tenant_id=tenant_id, to_phone=from_number, text=final_text)
        except Exception as e:
            print("ERRO AO ENVIAR WHATSAPP (ai):", str(e))
        return {"status": "ok", "flow": "ai", "intent": assistant_json.get("intent")}

    conversa = (
        db.query(Conversation)
        .filter_by(tenant_id=tenant_id, telefone=from_number)
        .first()
    )

    if not conversa:
        conversa = Conversation(tenant_id=tenant_id, telefone=from_number)
        resposta = iniciar_conversa(conversa, db, tenant_id)
        db.add(conversa)
        db.commit()

        try:
            service.send_text(db, tenant_id=tenant_id, to_phone=from_number, text=resposta)
        except Exception as e:
            print("ERRO AO ENVIAR WHATSAPP (start):", str(e))

        return {"status": "ok", "flow": "started"}

    resposta = processar_mensagem(conversa, text, db, tenant_id)
    db.commit()

    try:
        estado = getattr(conversa, "estado", "")
        last_order_id = getattr(conversa, "last_order_id", None)

        if estado == "PEDIDO_CRIADO" and not last_order_id:
            order = create_order_from_conversation(
                db,
                tenant_id,
                conversa,
                contact_name=contact_name,
            )

            try:
                conversa.last_order_id = order.id
                db.commit()
            except Exception:
                pass

            auto_print, printer_name = _get_print_settings(tenant_id, db)
            os.environ["AUTO_PRINT"] = "1" if auto_print else "0"
            if printer_name:
                os.environ["PRINTER_NAME"] = printer_name

            settings_path = os.path.join("data", f"print_settings_tenant_{tenant_id}.json")
            if os.path.exists(settings_path):
                print_settings = get_print_settings(tenant_id)
            else:
                print_settings = {
                    "auto_print": auto_print,
                    "mode": "pdf",
                    "printer_name": printer_name,
                }

            pdf_path = auto_print_if_possible(order, tenant_id, config=print_settings)
            print("TICKET:", "ok", "PDF:", pdf_path)
    except Exception as e:
        print("ERRO AO SALVAR/GERAR ETIQUETA:", str(e))

    try:
        service.send_text(db, tenant_id=tenant_id, to_phone=from_number, text=resposta)
    except Exception as e:
        print("ERRO AO ENVIAR WHATSAPP (continued):", str(e))

    return {"status": "ok", "flow": "continued"}


@router.get("/api/whatsapp/{tenant_id}/webhook")
async def verify_webhook_tenant(tenant_id: int, request: Request, db: Session = Depends(get_db)):
    qp = request.query_params
    mode = qp.get("hub.mode")
    token = qp.get("hub.verify_token")
    challenge = qp.get("hub.challenge")

    if mode == "subscribe" and _verify_tenant_token(db, tenant_id, token):
        return PlainTextResponse(challenge or "")

    raise HTTPException(status_code=403, detail="Verify token inválido")


@router.post("/api/whatsapp/{tenant_id}/webhook")
async def whatsapp_webhook_tenant(tenant_id: int, request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    messages = parse_cloud_webhook(payload)
    if not messages:
        return {"status": "ignored"}

    last_response = None
    for extracted in messages:
        last_response = _handle_inbound_message(
            db,
            tenant_id=tenant_id,
            message_id=extracted["message_id"],
            from_number=extracted["from_number"],
            text=extracted.get("text", ""),
            message_type=extracted.get("message_type", "text"),
            contact_name=extracted.get("contact_name"),
            phone_number_id=extracted.get("phone_number_id"),
        )

    return last_response or {"status": "ok"}


@router.post("/webhook")
async def whatsapp_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    extracted = _extract_message(payload)
    if not extracted:
        return {"status": "ignored"}

    return _handle_inbound_message(
        db,
        tenant_id=1,
        message_id=extracted["message_id"],
        from_number=extracted["from_number"],
        text=extracted["text"],
        message_type="text",
        contact_name=extracted.get("contact_name"),
        phone_number_id=extracted.get("phone_number_id"),
    )


@router.post("/webhook/whatsapp")
async def whatsapp_webhook_public(request: Request):
    payload = await request.json()
    logger.info("WhatsApp webhook recebido: %s", payload)
    return {"ok": True}
