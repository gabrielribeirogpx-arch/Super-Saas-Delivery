import asyncio
import json
import httpx

from app.core.config import META_WA_ACCESS_TOKEN, META_WA_PHONE_NUMBER_ID, META_API_VERSION


class WhatsAppSendError(RuntimeError):
    def __init__(self, status_code: int, body_text: str):
        super().__init__(f"Erro WhatsApp {status_code}: {body_text}")
        self.status_code = status_code
        self.body_text = body_text


def _should_retry(status_code: int, body_text: str) -> bool:
    # Erros temporários / instabilidade
    if status_code in (500, 502, 503, 504):
        return True

    # Erro genérico frequente do Cloud API
    try:
        data = json.loads(body_text or "{}")
        code = ((data.get("error") or {}).get("code"))
        if code == 131000:
            return True
    except Exception:
        pass

    return False


def _backoff_seconds(attempt: int) -> float:
    # 1s, 2s, 4s... (máx 8s)
    sec = 1.0 * (2 ** max(0, attempt - 1))
    return min(sec, 8.0)


async def send_text(
    to: str,
    text: str,
    phone_number_id: str | None = None,
    access_token: str | None = None,
    retries: int = 3,
    timeout: float = 20.0,
):
    token = access_token or META_WA_ACCESS_TOKEN
    phone_id = phone_number_id or META_WA_PHONE_NUMBER_ID

    if not token or not phone_id:
        raise RuntimeError("Faltam META_WA_ACCESS_TOKEN ou META_WA_PHONE_NUMBER_ID no .env")

    url = f"https://graph.facebook.com/{META_API_VERSION}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, retries + 1):
            try:
                r = await client.post(url, headers=headers, json=payload)
                body_text = r.text

                # sucesso
                if 200 <= r.status_code < 300:
                    try:
                        return r.json()
                    except Exception:
                        return {"ok": True, "raw": body_text}

                # erro com retry
                if _should_retry(r.status_code, body_text) and attempt < retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue

                # erro final
                raise WhatsAppSendError(r.status_code, body_text)

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise

            except Exception as e:
                last_error = e
                raise

    # fallback (não deve chegar aqui)
    if last_error:
        raise last_error
    raise RuntimeError("Falha desconhecida ao enviar WhatsApp")
