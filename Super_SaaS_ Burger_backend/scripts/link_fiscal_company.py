"""Link an existing Focus company to a verified store (internal operation)."""

import argparse
import os

import httpx
from sqlalchemy.exc import IntegrityError

import app.models
from app.core.database import SessionLocal
from app.models.fiscal_profile import FiscalProfile
from app.services.focus_companies import get_homologation_token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tenant_id", type=int)
    parser.add_argument("company_id", type=int)
    args = parser.parse_args()
    master = os.getenv("FOCUS_NFE_MASTER_TOKEN", "").strip()
    if not master or args.tenant_id < 1 or args.company_id < 1:
        parser.error("Configure FOCUS_NFE_MASTER_TOKEN e informe IDs válidos.")

    try:
        with SessionLocal() as db:
            profile = db.query(FiscalProfile).filter_by(tenant_id=args.tenant_id).with_for_update().one_or_none()
            if profile is None:
                parser.error("A loja precisa de um cadastro fiscal.")
            if profile.focus_company_id not in (None, args.company_id):
                parser.error("A loja já está vinculada a outro emitente.")
            with httpx.Client(timeout=25, trust_env=False) as client:
                get_homologation_token(client, master, args.company_id, profile.cnpj)
            profile.focus_company_id = args.company_id
            db.commit()
    except (httpx.HTTPError, ValueError):
        parser.error("Não foi possível confirmar o emitente de homologação para o CNPJ da loja.")
    except IntegrityError:
        parser.error("O emitente já está vinculado a outra loja.")
    print("Emitente vinculado à loja.")


if __name__ == "__main__":
    main()
