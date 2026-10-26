from __future__ import annotations

from typing import Any


class GeminiProvider:
    name = "gemini"

    def generate(
        self,
        tenant_id: int,
        phone: str,
        user_message: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "intent": "HELP",
            "tool_calls": [],
            "message_to_user": "O provedor Gemini ainda não está configurado. Posso ajudar com o cardápio ou pedidos.",
            "confidence": 0.3,
        }
