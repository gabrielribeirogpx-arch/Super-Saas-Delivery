from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from app.core.request_context import get_request_id, get_tenant_id, get_user_id

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

_SENSITIVE_PATTERNS = [
    re.compile(r"(authorization\s*[:=]\s*bearer\s+)([^\s\"]+)", re.IGNORECASE),
    re.compile(r"(token\s*[:=]\s*)([^\s\",}]+)", re.IGNORECASE),
    re.compile(r"(password\s*[:=]\s*)([^\s\",}]+)", re.IGNORECASE),
    re.compile(r"(secret\s*[:=]\s*)([^\s\",}]+)", re.IGNORECASE),
]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", None) or get_request_id(),
            "tenant_id": getattr(record, "tenant_id", None) or get_tenant_id(),
            "user_id": getattr(record, "user_id", None) or get_user_id(),
            "module": record.name,
            "message": self._mask(self.formatMessage(record)),
            "duration_ms": getattr(record, "duration_ms", None),
        }
        endpoint = getattr(record, "endpoint", None)
        method = getattr(record, "method", None)
        status_code = getattr(record, "status_code", None)
        if endpoint is not None:
            payload["endpoint"] = endpoint
        if method is not None:
            payload["method"] = method
        if status_code is not None:
            payload["status_code"] = status_code
        return json.dumps(payload, ensure_ascii=False)

    def _mask(self, value: str) -> str:
        masked = value
        for pattern in _SENSITIVE_PATTERNS:
            masked = pattern.sub(r"\1***", masked)
        return masked


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler()
    formatter = JsonFormatter("%(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(logger_name).setLevel(LOG_LEVEL)
