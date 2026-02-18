from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class EndpointMetric:
    total_requests: int = 0
    total_duration_ms: float = 0.0
    error_count: int = 0


class InMemoryRequestMetrics:
    def __init__(self) -> None:
        self._metrics: dict[tuple[str, str], EndpointMetric] = {}
        self._lock = Lock()

    def observe(self, endpoint: str, method: str, status_code: int, duration_ms: float) -> None:
        key = (endpoint, method)
        with self._lock:
            metric = self._metrics.setdefault(key, EndpointMetric())
            metric.total_requests += 1
            metric.total_duration_ms += duration_ms
            if status_code >= 400:
                metric.error_count += 1

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        with self._lock:
            result: dict[str, dict[str, float | int]] = {}
            for (endpoint, method), metric in self._metrics.items():
                avg = metric.total_duration_ms / metric.total_requests if metric.total_requests else 0.0
                result[f"{method} {endpoint}"] = {
                    "total_requests": metric.total_requests,
                    "total_duration_ms": round(metric.total_duration_ms, 2),
                    "avg_duration_ms": round(avg, 2),
                    "error_count": metric.error_count,
                }
            return result


request_metrics = InMemoryRequestMetrics()
