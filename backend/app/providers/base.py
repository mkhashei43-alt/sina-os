"""LLM provider abstraction."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class ToolCallSpec:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCallSpec] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    finish_reason: str = ""


StreamCb = Callable[[str], Awaitable[None]]


class LLMProvider:
    name = "base"

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        stream_cb: StreamCb | None = None,
        purpose: str = "chat",
        payload_max_tokens: int | None = None,
    ) -> LLMResponse:  # pragma: no cover
        raise NotImplementedError

    async def complete_text(self, messages: list[dict], *, model: str, temperature: float = 0.0) -> LLMResponse:
        return await self.chat(messages, model=model, temperature=temperature, purpose="utility")
