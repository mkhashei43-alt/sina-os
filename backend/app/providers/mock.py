"""Deterministic test double for the LLM.

Used by the test-suite and by `SINA_LLM=mock` demo mode so the full agent loop
(planning → tool calls → verification → report) can be exercised end-to-end
without an external API key. It is NOT a language model: it replays a small
scripted policy keyed on the task instruction.
"""
from __future__ import annotations

import hashlib
import json
import re

from .base import LLMProvider, LLMResponse, StreamCb, ToolCallSpec, Usage


def _cid(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.md5(seed.encode()).hexdigest()[:10]}"


class MockProvider(LLMProvider):
    name = "mock"

    @property
    def configured(self) -> bool:
        return True

    async def chat(self, messages, *, model, tools=None, temperature=0.2, stream_cb: StreamCb | None = None, purpose="chat", payload_max_tokens: int | None = None) -> LLMResponse:
        tool_names = {t["function"]["name"] for t in (tools or [])}
        instruction = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                instruction = m.get("content") or ""
                break
        # count prior tool executions in this run
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        step = len(tool_msgs)

        script = self._scripts(instruction, tool_names)
        if step < len(script):
            call = script[step]
            resp = LLMResponse(
                content="" if call else "در حال اجرا…",
                tool_calls=[call] if call else [],
                usage=Usage(50, 20, 0.0), model=model, finish_reason="tool_calls",
            )
        else:
            text = self._final_report(instruction, messages)
            if stream_cb:
                for chunk in re.findall(r".{1,40}", text, flags=re.S):
                    await stream_cb(chunk)
            resp = LLMResponse(content=text, usage=Usage(80, 60, 0.0), model=model, finish_reason="stop")
        return resp

    # ---------- scripted policies ----------
    def _scripts(self, instruction: str, available: set[str]) -> list[ToolCallSpec | None]:
        ins = instruction.lower()
        scripts: list[ToolCallSpec | None] = []
        want_python = any(k in ins for k in ("python", "پایتون", "script", "برنامه", "تست", "test"))
        if want_python:
            if "files" in available:
                scripts.append(ToolCallSpec(
                    id=_cid("call", "w1"), name="files",
                    arguments={"operation": "write", "path": "app/calculator.py", "content": (
                        '"""Simple calculator app created by Sina AI OS."""\n\n\n'
                        "def add(a, b):\n    return a + b\n\n\n"
                        "def sub(a, b):\n    return a - b\n\n\n"
                        "def mul(a, b):\n    return a * b\n\n\n"
                        "def div(a, b):\n"
                        "    if b == 0:\n        raise ValueError('division by zero')\n"
                        "    return a / b\n\n\n"
                        "if __name__ == '__main__':\n"
                        "    print('calculator ready:', add(2, 3))\n"
                    )}))
                scripts.append(ToolCallSpec(
                    id=_cid("call", "w2"), name="files",
                    arguments={"operation": "write", "path": "tests/test_calculator.py", "content": (
                        "import sys, pathlib\n"
                        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))\n"
                        "from app.calculator import add, sub, mul, div\n\n\n"
                        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
                        "def test_sub():\n    assert sub(5, 3) == 2\n\n\n"
                        "def test_mul():\n    assert mul(3, 4) == 12\n\n\n"
                        "def test_div_zero():\n"
                        "    try:\n        div(1, 0)\n    except ValueError:\n        return\n"
                        "    raise AssertionError('expected ValueError')\n"
                    )}))
                scripts.append(ToolCallSpec(
                    id=_cid("call", "w3"), name="files",
                    arguments={"operation": "write", "path": "README.md",
                               "content": "# Calculator App\n\nCreated and verified by Sina AI OS agent.\n"}))
            if "python_exec" in available:
                scripts.append(ToolCallSpec(id=_cid("call", "x1"), name="python_exec",
                                            arguments={"operation": "run_file", "path": "app/calculator.py"}))
                scripts.append(ToolCallSpec(id=_cid("call", "x2"), name="python_exec",
                                            arguments={"operation": "run_file", "path": "tests/test_calculator.py"}))
            if "terminal" in available:
                scripts.append(ToolCallSpec(id=_cid("call", "t1"), name="terminal",
                                            arguments={"command": "python3 -m pytest -q tests/ || true"}))
            if "workspace" in available:
                scripts.append(ToolCallSpec(id=_cid("call", "ws"), name="workspace",
                                            arguments={"operation": "tree"}))
            return scripts

        if any(k in ins for k in ("جستجو", "search", "research", "تحقیق", "خبر")):
            if "web_search" in available:
                return [ToolCallSpec(id=_cid("call", "s1"), name="web_search", arguments={"query": instruction[:150], "limit": 3})]
            return []

        if any(k in ins for k in ("سلام", "hello", "hi")):
            return []
        return []

    def _final_report(self, instruction: str, messages: list[dict]) -> str:
        tool_summaries = []
        for m in messages:
            if m.get("role") == "tool":
                name = (m.get("name") or "tool")
                body = (m.get("content") or "")[:300].replace("\n", " ")
                tool_summaries.append(f"- `{name}` → {body}")
        head = "✅ **گزارش نهایی (حالت آزمون mock)**\n\n"
        body = "کار درخواستی با اجرای واقعی ابزارها در فضای‌کار ایزوله انجام و راستی‌آزمایی شد.\n\n"
        if tool_summaries:
            body += "**ابزارهای اجراشده:**\n" + "\n".join(tool_summaries) + "\n\n"
        body += f"**دستور:** {instruction[:300]}\n"
        return head + body
