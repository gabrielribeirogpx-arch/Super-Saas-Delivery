"""Preview or submit one test order to Focus NFC-e homologation."""

import argparse
import json
import os
import re
from pathlib import Path

import httpx
from pydantic import TypeAdapter, ValidationError

import app.models
from app.core.database import SessionLocal
from app.services.focus_nfce import FiscalProduct, prepare_payload, submit_or_consult


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("order_id", type=int)
    parser.add_argument("products", type=Path, help="JSON fiscal por ID de produto")
    parser.add_argument("--submit", action="store_true", help="enviar somente à homologação da Focus")
    args = parser.parse_args()

    tenant = os.getenv("FOCUS_NFCE_PILOT_TENANT_ID", "")
    namespace = os.getenv("FOCUS_NFCE_PILOT_NAMESPACE", "")
    token = os.getenv("FOCUS_NFCE_HOMOLOGATION_TOKEN", "").strip()
    if not re.fullmatch(r"[1-9][0-9]{0,9}", tenant) or not re.fullmatch(r"[A-Za-z0-9]{1,20}", namespace):
        parser.error("configure o ID da loja piloto e um namespace alfanumérico exclusivo da base")
    if args.order_id <= 0 or (args.submit and not token):
        parser.error("informe um ID de pedido válido e configure o token de homologação para enviar")
    ref = f"FZ{namespace}T{tenant}O{args.order_id}"

    try:
        products = TypeAdapter(dict[int, FiscalProduct]).validate_json(args.products.read_bytes())
    except (OSError, ValidationError):
        parser.error("não foi possível carregar o JSON de dados fiscais dos produtos")
    try:
        with SessionLocal() as db:
            payload = prepare_payload(db, int(tenant), args.order_id, products)
        if not args.submit:
            print(json.dumps({"ref": ref, "ambiente": "homologacao", "payload": payload}, ensure_ascii=False))
            return 0
        with httpx.Client(timeout=25, trust_env=False) as client:
            result = submit_or_consult(client, token, ref, payload)
    except httpx.HTTPStatusError as exc:
        parser.error(f"Focus retornou HTTP {exc.response.status_code} para {ref}; consulte a referência no portal.")
    except httpx.RequestError:
        parser.error(f"Falha de comunicação para {ref}. Repita com a mesma referência para consultar antes de enviar.")
    except ValueError as exc:
        parser.error(str(exc))

    fields = ("status", "status_sefaz", "mensagem_sefaz", "chave_nfe", "caminho_xml_nota_fiscal", "caminho_danfe")
    print(json.dumps({"ref": ref, **{field: result[field] for field in fields if field in result}}, ensure_ascii=False))
    return 0 if result["status"] == "autorizado" else 1


if __name__ == "__main__":
    raise SystemExit(main())
