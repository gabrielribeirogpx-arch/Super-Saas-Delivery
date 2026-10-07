import json
import logging

from uvicorn.config import LOGGING_CONFIG
from logging.config import dictConfig

from app.core.logging_setup import configure_logging


def test_real_uvicorn_access_handler_uses_application_redaction(capsys):
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access"]
    previous = {name: (list(logging.getLogger(name).handlers), logging.getLogger(name).level,
                       logging.getLogger(name).propagate) for name in names}
    try:
        dictConfig(LOGGING_CONFIG)
        configure_logging()
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d',
            "127.0.0.1", "POST", "/api/webhooks/billing/kiwify?signature=synthetic-private-marker", "1.1", 202)
        output = capsys.readouterr().err
        assert "synthetic-private-marker" not in output
        record = json.loads(output)
        assert record["module"] == "uvicorn.access"
        assert "signature=[REDACTED]" in record["message"]
    finally:
        for name, (handlers, level, propagate) in previous.items():
            logger = logging.getLogger(name)
            logger.handlers[:] = handlers
            logger.setLevel(level)
            logger.propagate = propagate
