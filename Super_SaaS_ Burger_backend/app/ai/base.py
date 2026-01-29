from __future__ import annotations

from typing import Any, Protocol


class AIProvider(Protocol):
    def generate(
        self,
        tenant_id: int,
        phone: str,
        user_message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        ...
