from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from threading import Lock

DEFAULT_LIMIT = 1000
DEFAULT_WINDOW_SECONDS = 60


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int


class RateLimiterService(ABC):
    @abstractmethod
    def check(self, *, tenant_id: str, endpoint: str) -> RateLimitDecision:
        """Valida se a requisição do tenant para o endpoint deve prosseguir."""


class InMemoryRateLimiterService(RateLimiterService):
    """Rate limit em memória por tenant+endpoint.

    Estrutura com interface para futura troca por Redis/distribuído.
    """

    def __init__(self, *, limit: int = DEFAULT_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._store: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    def check(self, *, tenant_id: str, endpoint: str) -> RateLimitDecision:
        now = time.monotonic()
        key = (tenant_id, endpoint)

        with self._lock:
            bucket = self._store.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            bucket.append(now)
            remaining = max(0, self.limit - len(bucket))
            return RateLimitDecision(
                allowed=True,
                limit=self.limit,
                remaining=remaining,
                retry_after_seconds=0,
            )
