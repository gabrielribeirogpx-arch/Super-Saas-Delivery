"""Railway cron: every minute. Never logs provider exceptions or payloads."""
from pathlib import Path
import logging
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.database import SessionLocal
from app.core.hotmart_config import hotmart_settings
from app.services.hotmart_worker import run_cycle

def main():
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        result=run_cycle(SessionLocal,hotmart_settings(),reconcile=True)
        print("Hotmart billing cycle:",result)
        return 1 if result["errors"] else 0
    except Exception:
        print("Hotmart billing cycle failed; retry required")
        return 1
if __name__=="__main__":
    raise SystemExit(main())
