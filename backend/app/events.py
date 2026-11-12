"""Event bus: in-process pub/sub with optional Redis bridge between API and worker."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from .config import get_settings

log = logging.getLogger("sina.events")


class EventBroker:
    """Topic-based pub/sub. Single-process: asyncio queues. With REDIS_URL: pub/sub bridge."""

    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._redis = None
        self._redis_task: asyncio.Task | None = None

    async def start(self) -> None:
        settings = get_settings()
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
                self._redis_task = asyncio.create_task(self._redis_reader())
                log.info("redis event bridge started")
            except Exception as e:  # pragma: no cover
                log.warning("redis unavailable, falling back to in-process events: %s", e)
                self._redis = None

    async def stop(self) -> None:
        if self._redis_task:
            self._redis_task.cancel()
        if self._redis:
            await self._redis.aclose()

    async def _redis_reader(self) -> None:  # pragma: no cover
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe("sina:*")
        async for msg in pubsub.listen():
            if msg.get("type") != "pmessage":
                continue
            topic = msg["channel"][len("sina:"):]
            try:
                await self._publish_local(topic, json.loads(msg["data"]))
            except Exception:
                continue

    async def publish(self, topic: str, event: str, data: dict[str, Any] | None = None) -> None:
        payload = {"event": event, "data": data or {}}
        await self._publish_local(topic, payload)
        if self._redis:
            try:
                await self._redis.publish(f"sina:{topic}", json.dumps(payload, default=str))
            except Exception as e:  # pragma: no cover
                log.warning("redis publish failed: %s", e)

    async def _publish_local(self, topic: str, payload: dict) -> None:
        for q in list(self._subs.get(topic, set())):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, *topics: str, heartbeat: float = 15.0) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        for t in topics:
            self._subs.setdefault(t, set()).add(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=heartbeat)
                    yield item
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": {}}
        finally:
            for t in topics:
                self._subs.get(t, set()).discard(q)
                if not self._subs.get(t):
                    self._subs.pop(t, None)


broker = EventBroker()
