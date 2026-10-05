from __future__ import annotations

import hashlib
import re


_PUBLIC_TRACKING_PATH = re.compile(
    r"(?P<prefix>/(?:api/)?(?:public/(?:order|track|tracking|sse)|sse/delivery|api/sse/delivery|api/orders/by-token)/)"
    r"(?P<token>[^/?\s]+)",
    re.IGNORECASE,
)


def tracking_token_fingerprint(raw_token: str) -> str:
    """Return a stable, non-reversible identifier suitable for application logs."""
    token = str(raw_token or "").strip()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12] if token else "empty"


def redact_public_tracking_tokens(value: str) -> str:
    """Replace credentials embedded in public tracking URLs with their fingerprint."""

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group('prefix')}:token-{tracking_token_fingerprint(match.group('token'))}"

    return _PUBLIC_TRACKING_PATH.sub(_replace, str(value))
