"""Long-term memory: structured recall + optional semantic embeddings."""
from __future__ import annotations

import math
import re
from collections import Counter

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Memory

_TOKEN = re.compile(r"[\w\u0600-\u06FF]{2,}")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


async def embed(text: str) -> list[float] | None:
    s = get_settings()
    if not s.embeddings_base_url or not s.embeddings_api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{s.embeddings_base_url.rstrip('/')}/embeddings",
                headers={"Authorization": f"Bearer {s.embeddings_api_key}"},
                json={"model": s.embeddings_model, "input": text[:6000]},
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
    except Exception:
        return None


async def remember(
    db: AsyncSession, *, user_id: str, content: str, kind: str = "fact",
    project_id: str | None = None, tags: list[str] | None = None,
    importance: float = 0.5, source: str = "agent",
) -> Memory:
    emb = await embed(content)
    mem = Memory(user_id=user_id, project_id=project_id, kind=kind, content=content.strip()[:8000],
                 tags=tags or [], importance=importance, embedding=emb, source=source)
    db.add(mem)
    await db.commit()
    await db.refresh(mem)
    return mem


async def recall(
    db: AsyncSession, *, user_id: str, query: str, project_id: str | None = None,
    limit: int = 6, min_score: float = 0.12,
) -> list[tuple[float, Memory]]:
    """Hybrid retrieval: embedding cosine if available, else lexical overlap + recency."""
    rows = list((await db.execute(
        select(Memory).where(Memory.user_id == user_id).order_by(Memory.created_at.desc()).limit(500)
    )).scalars())
    if not rows:
        return []
    q_emb = await embed(query)
    q_tokens = Counter(tokens(query))
    scored: list[tuple[float, Memory]] = []
    for m in rows:
        score = 0.0
        if q_emb and m.embedding:
            score = cosine(q_emb, m.embedding)
        if score < 0.05:
            m_tokens = Counter(tokens(m.content))
            overlap = sum(min(q_tokens[t], m_tokens[t]) for t in q_tokens)
            score = overlap / (sum(q_tokens.values()) or 1)
        score += 0.05 * float(m.importance or 0)
        if project_id and m.project_id == project_id:
            score += 0.15
        if score >= min_score:
            scored.append((score, m))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def format_memories(items: list[tuple[float, Memory]]) -> str:
    if not items:
        return ""
    lines = ["## حافظه مرتبط (از کارهای قبلی)"]
    for score, m in items:
        lines.append(f"- [{m.kind}] {m.content[:400]}")
    return "\n".join(lines)
