"""Provider factory."""
from __future__ import annotations

import os

from ..config import get_settings
from .base import LLMProvider, LLMResponse, ToolCallSpec, Usage
from .mock import MockProvider
from .openrouter import OpenRouterProvider


def get_provider() -> LLMProvider:
    """SINA_LLM=mock forces the deterministic test provider; otherwise OpenRouter."""
    if os.getenv("SINA_LLM", "").lower() == "mock":
        return MockProvider()
    s = get_settings()
    if s.openrouter_api_key:
        return OpenRouterProvider()
    return MockProvider()


def select_model(purpose: str = "chat") -> str:
    s = get_settings()
    if purpose == "code":
        return s.coding_model
    if purpose == "reason":
        return s.reasoning_model
    return s.default_model


__all__ = ["LLMProvider", "LLMResponse", "ToolCallSpec", "Usage", "get_provider", "select_model", "OpenRouterProvider", "MockProvider"]


async def chat_resilient(provider: LLMProvider, messages: list[dict], *, model: str,
                         tools: list[dict] | None = None, stream_cb=None, purpose: str = "chat",
                         temperature: float = 0.2):
    """Try the primary model, then configured fallbacks. Raises only if all fail."""
    s = get_settings()
    chain = [model] + [m for m in s.fallbacks if m != model]
    last: Exception | None = None
    for i, m in enumerate(chain):
        try:
            return await provider.chat(messages, model=m, tools=tools, stream_cb=stream_cb,
                                       purpose=purpose, temperature=temperature)
        except Exception as e:  # provider/network/quota
            last = e
            if i < len(chain) - 1:
                import logging
                logging.getLogger("sina.provider").warning("model %s failed (%s) → fallback %s", m, str(e)[:120], chain[i + 1])
                if stream_cb:  # avoid duplicated partial text from a failed attempt
                    stream_cb = None
                continue
    raise last  # type: ignore[misc]
