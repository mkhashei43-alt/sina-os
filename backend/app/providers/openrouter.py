"""OpenRouter provider: streaming, tool calling, retries, usage+cost tracking."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from ..config import get_settings
from .base import LLMProvider, LLMResponse, StreamCb, ToolCallSpec, Usage

log = logging.getLogger("sina.openrouter")

# Approximate fallback prices ($ / 1M tokens) if the API does not return pricing.
_PRICE_HINTS = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "openai/o3-mini": (1.10, 4.40),
    "deepseek/deepseek-chat": (0.27, 1.10),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
}


class OpenRouterError(RuntimeError):
    pass


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        s = get_settings()
        self.api_key = api_key or s.openrouter_api_key
        self.base_url = (base_url or s.openrouter_base_url).rstrip("/")
        self.timeout = s.llm_timeout_seconds
        self.retries = s.llm_max_retries
        self.referer = s.openrouter_referer

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referer,
            "X-Title": "Sina AI OS",
        }

    @staticmethod
    def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
        if model.endswith(":free"):
            return 0.0  # free tier models are billed at zero
        pin, pout = _PRICE_HINTS.get(model, (1.0, 3.0))
        return round(tokens_in / 1e6 * pin + tokens_out / 1e6 * pout, 6)

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self.base_url}/models", headers=self._headers())
            r.raise_for_status()
            data = r.json().get("data", [])
        return [
            {
                "id": m.get("id"),
                "name": m.get("name", m.get("id")),
                "context": m.get("context_length"),
                "pricing": m.get("pricing", {}),
            }
            for m in data
        ]

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
    ) -> LLMResponse:
        if not self.api_key:
            raise OpenRouterError("OPENROUTER_API_KEY is not configured")

        s_cfg = get_settings()
        payload: dict[str, Any] = {
            "model": model, "messages": messages, "temperature": temperature,
            "max_tokens": int(payload_max_tokens or s_cfg.llm_max_tokens),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        use_stream = stream_cb is not None
        payload["stream"] = use_stream
        if use_stream:  # ask for usage on the final chunk
            payload["stream_options"] = {"include_usage": True}

        last_err: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                if use_stream:
                    return await self._stream_chat(payload, model, stream_cb)
                return await self._once_chat(payload, model)
            except (httpx.TimeoutException, httpx.NetworkError, OpenRouterError) as e:
                last_err = e
                wait = min(2 ** attempt, 20)
                log.warning("openrouter attempt %s/%s failed: %s — retrying in %ss", attempt, self.retries, e, wait)
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                code = e.response.status_code
                body = e.response.text[:500]
                if code == 402:  # out of credits — retrying cannot help
                    raise OpenRouterError(
                        f"موجودی حساب OpenRouter کافی نیست (402). اعتبار حساب را افزایش دهید یا از مدل رایگان (:free) استفاده کنید. جزئیات: {body[:300]}"
                    ) from e
                if code in (401, 403, 404):
                    raise OpenRouterError(f"OpenRouter HTTP {code}: {body}") from e
                if code == 429 and "free-models-per-day" in body:
                    # سهمیهٔ روزانهٔ مدل‌های رایگان تمام شده — تلاش مجدد بی‌فایده است
                    raise OpenRouterError(
                        "سهمیهٔ روزانهٔ مدل‌های رایگان OpenRouter تمام شده است. "
                        "برای ادامه: اعتبار حساب OpenRouter را افزایش دهید، مدل غیررایگان تنظیم کنید، "
                        "یا کلید OpenRouter خودتان را در بخش اتصال‌ها ثبت کنید."
                    ) from e
                if code in (429, 502, 503, 504) and attempt < self.retries:
                    await asyncio.sleep(min(2 ** attempt, 20))
                    last_err = e
                    continue
                raise OpenRouterError(f"OpenRouter HTTP {code}: {body}") from e
        raise OpenRouterError(f"OpenRouter failed after {self.retries} attempts: {last_err}")

    async def _once_chat(self, payload: dict, model: str) -> LLMResponse:
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            r.raise_for_status()
            body = r.json()
        choice = (body.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        usage_raw = body.get("usage") or {}
        tin = int(usage_raw.get("prompt_tokens") or 0)
        tout = int(usage_raw.get("completion_tokens") or 0)
        cost = float(usage_raw.get("total_cost") or 0) or self.estimate_cost(model, tin, tout)
        calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {"_raw": fn.get("arguments")}
            calls.append(ToolCallSpec(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))
        content = msg.get("content") or ""
        if not content and msg.get("reasoning"):
            content = msg["reasoning"]  # reasoning-style models
        return LLMResponse(content=content, tool_calls=calls,
                           usage=Usage(tin, tout, cost), model=body.get("model", model),
                           finish_reason=choice.get("finish_reason") or "")

    async def _stream_chat(self, payload: dict, model: str, stream_cb: StreamCb) -> LLMResponse:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_acc: dict[int, dict] = {}
        usage = Usage()
        finish = ""
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            async with c.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload) as r:
                if r.status_code >= 400:
                    text = (await r.aread()).decode(errors="replace")[:500]
                    raise OpenRouterError(f"OpenRouter HTTP {r.status_code}: {text}")
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("usage"):
                        usage.tokens_in = int(chunk["usage"].get("prompt_tokens") or 0)
                        usage.tokens_out = int(chunk["usage"].get("completion_tokens") or 0)
                        usage.cost_usd = float(chunk["usage"].get("total_cost") or 0)
                    for choice in chunk.get("choices") or []:
                        finish = choice.get("finish_reason") or finish
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            content_parts.append(delta["content"])
                            await stream_cb(delta["content"])
                        elif delta.get("reasoning"):
                            # reasoning models stream thinking instead of content
                            reasoning_parts.append(delta["reasoning"])
                            await stream_cb(delta["reasoning"])
                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            acc = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                            if tc.get("id"):
                                acc["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                acc["name"] += fn["name"]
                            if fn.get("arguments"):
                                acc["arguments"] += fn["arguments"]
        calls = []
        for idx in sorted(tool_acc):
            acc = tool_acc[idx]
            try:
                args = json.loads(acc["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"_raw": acc["arguments"]}
            calls.append(ToolCallSpec(id=acc["id"] or f"call_{idx}", name=acc["name"], arguments=args))
        if not usage.cost_usd:
            usage.cost_usd = self.estimate_cost(model, usage.tokens_in, usage.tokens_out)
        text = "".join(content_parts) or "".join(reasoning_parts)
        return LLMResponse(content=text, tool_calls=calls, usage=usage, model=model, finish_reason=finish)
