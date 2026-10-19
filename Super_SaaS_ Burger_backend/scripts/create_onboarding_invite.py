"""Operator console only. Prints an intentional one-use customer invitation, never API secrets."""
from pathlib import Path
import argparse
import sys
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.core.hotmart_config import hotmart_settings
from app.services.onboarding_invites import issue_invite

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--origin',required=True,help='Public frontend origin, e.g. https://staging.fomizero.com.br')
    args=parser.parse_args()
    parts=urlsplit(args.origin)
    if parts.scheme!='https' or not parts.netloc or parts.username or parts.password or parts.path not in {'','/'} or parts.query or parts.fragment:
        raise RuntimeError('Use the HTTPS origin of your Fomizero frontend')
    if not hotmart_settings().enabled:
        raise RuntimeError('Configure Hotmart billing before issuing signup invitations')
    with SessionLocal() as db,db.begin():token=issue_invite(db)
    print(args.origin.rstrip('/')+'/onboarding#invite='+token)
    print('Convite válido por sete dias e um cadastro. Compartilhe apenas com o restaurante convidado.')
    return 0
if __name__=='__main__':raise SystemExit(main())
