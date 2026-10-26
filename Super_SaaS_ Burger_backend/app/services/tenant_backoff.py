from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Lock


@dataclass
class BackoffDecision:
    delay_seconds: float
    consecutive_failures: int


class TenantBackoffService(ABC):
    @abstractmethod
    def before_request(self, *, tenant_id: int, integration: str) -> BackoffDecision:
        """Retorna delay aplicável antes da chamada externa."""

    @abstractmethod
    def register_success(self, *, tenant_id: int, integration: str) -> None:
        """Reseta estado de falhas consecutivas."""

    @abstractmethod
    def register_failure(self, *, tenant_id: int, integration: str) -> int:
        """Incrementa falhas consecutivas e retorna total atual."""


class InMemoryTenantBackoffService(TenantBackoffService):
    def __init__(self, *, threshold: int = 3, max_backoff_seconds: float = 8.0) -> None:
        self.threshold = threshold
        self.max_backoff_seconds = max_backoff_seconds
        self._failures: dict[tuple[int, str], int] = {}
        self._last_failure_at: dict[tuple[int, str], float] = {}
        self._lock = Lock()

    def before_request(self, *, tenant_id: int, integration: str) -> BackoffDecision:
        key = (tenant_id, integration)
        with self._lock:
            failures = self._failures.get(key, 0)
            if failures < self.threshold:
                return BackoffDecision(delay_seconds=0.0, consecutive_failures=failures)

            power = failures - self.threshold
            delay = min((2 ** power), self.max_backoff_seconds)
            return BackoffDecision(delay_seconds=float(delay), consecutive_failures=failures)

    def register_success(self, *, tenant_id: int, integration: str) -> None:
        key = (tenant_id, integration)
        with self._lock:
            self._failures.pop(key, None)
            self._last_failure_at.pop(key, None)

    def register_failure(self, *, tenant_id: int, integration: str) -> int:
        key = (tenant_id, integration)
        with self._lock:
            failures = self._failures.get(key, 0) + 1
            self._failures[key] = failures
            self._last_failure_at[key] = time.monotonic()
            return failures
