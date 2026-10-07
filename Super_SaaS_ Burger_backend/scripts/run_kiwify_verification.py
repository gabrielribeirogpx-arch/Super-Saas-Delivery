"""Railway cron entrypoint; python scripts/run_kiwify_verification.py."""
import logging
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.kiwify_config import kiwify_settings
import app.models
from app.services.kiwify_verification import KiwifyVerificationService
from app.services.kiwify_reconciliation import schedule_reconciliation


def main():
    settings = kiwify_settings()
    if not settings.enabled:
        print("Kiwify verification disabled")
        return 0
    # Do not emit integration exceptions or HTTP debug logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    service = KiwifyVerificationService(SessionLocal, settings)
    try:
        schedule_reconciliation(SessionLocal, settings, datetime.now(timezone.utc))
        results = service.run_pending(limit=50)
        print(f"Kiwify verification cycle completed: {len(results)} candidates")
        return 0
    except Exception:
        print("Kiwify verification cycle failed; retry required")
        return 1
    finally:
        service.source.close()


if __name__ == "__main__":
    raise SystemExit(main())
