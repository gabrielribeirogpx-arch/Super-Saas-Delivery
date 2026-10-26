from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str = Field(..., min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    intent: str = Field(..., min_length=1)
    tool_calls: List[ToolCall] = Field(default_factory=list)
    message_to_user: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
