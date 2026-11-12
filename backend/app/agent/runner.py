"""Agent orchestrator — LangGraph state machine.

User Request → Intent Analysis → Planning → Tool Selection → Tool Execution
→ Result Evaluation → Retry/Continue → Final Verification → Report

State is persisted in the tasks table after every node, so tasks survive
restarts; a paused task (awaiting approval) resumes from the exact tool call.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..events import broker
from ..models import (
    Approval, Conversation, Integration, Message, ModelUsage, Task, TaskStep, ToolCall, ToolResult, User, Workspace,
)
from ..crypto import decrypt_json
from ..providers import chat_resilient, get_provider, select_model
from ..providers.openrouter import OpenRouterProvider
from ..services.tenancy import enforce_token_budget
from ..security import sanitize_output
from ..services.memory import format_memories, recall
from ..tools import ToolContext, classify_risk, registry
from ..tools.base import ToolResult as _TR
from .prompts import PLANNER_PROMPT, SYSTEM_PROMPT

log = logging.getLogger("sina.agent")
_settings = get_settings()


class AgentState(TypedDict, total=False):
    task_id: str
    user_id: str
    instruction: str
    messages: list[dict]
    iteration: int
    tool_count: int
    pending_calls: list[dict]
    paused: bool
    analysis: dict
    plan: list[str]
    final_text: str
    last_error: str
    workspace: str
    project_id: str | None


# ------------------------------------------------------------------ helpers
async def _emit(task_id: str, event: str, data: dict | None = None) -> None:
    await broker.publish(f"task:{task_id}", event, data)


async def _add_step(db, task_id: str, phase: str, status: str, summary: str, detail: dict | None = None) -> None:
    rows = (await db.execute(select(TaskStep).where(TaskStep.task_id == task_id))).scalars().all()
    step = TaskStep(task_id=task_id, idx=len(rows), phase=phase, status=status,
                    summary=summary[:2000], detail=detail or {})
    db.add(step)
    await db.commit()
    await _emit(task_id, "task.step", {"phase": phase, "status": status, "summary": summary, "idx": step.idx})


def _jsonable(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


class TaskCancelled(Exception):
    pass


class AgentRunner:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.graph = self._build_graph()

    async def _apply_tenant_guards(self, db, task: Task) -> None:
        """کلید LLM اختصاصی مشتری + سقف توکن ماهانهٔ پلن."""
        user = (await db.execute(select(User).where(User.id == task.user_id))).scalar_one_or_none()
        if not user:
            return
        row = (await db.execute(select(Integration).where(
            Integration.user_id == user.id, Integration.kind == "openrouter",
            Integration.enabled == True))).scalar_one_or_none()  # noqa: E712
        if row:
            cfg = decrypt_json(row.config_enc)
            if cfg.get("api_key"):
                self.provider = OpenRouterProvider(api_key=cfg["api_key"])
                log.info("task %s uses the tenant's own OpenRouter key", task.id)
        try:
            await enforce_token_budget(db, user.tenant_id)
        except Exception as exc:  # HTTPException(429) from quota layer
            detail = getattr(exc, "detail", None) or str(exc)
            raise RuntimeError(str(detail)) from exc

    async def _add_step(self, db, task_id: str, phase: str, status: str, summary: str, detail: dict | None = None) -> None:
        await _add_step(db, task_id, phase, status, summary, detail)

    # ---------------------------------------------------------- graph
    def _build_graph(self):
        from langgraph.graph import END, START, StateGraph

        g = StateGraph(AgentState)
        g.add_node("analyze", self.node_analyze)
        g.add_node("make_plan", self.node_plan)
        g.add_node("act", self.node_act)
        g.add_node("verify", self.node_verify)
        g.add_node("report", self.node_report)
        g.add_edge(START, "analyze")
        g.add_edge("analyze", "make_plan")
        g.add_edge("make_plan", "act")
        g.add_conditional_edges("act", self._route_after_act, {"act": "act", "verify": "verify", "end": END})
        g.add_conditional_edges("verify", lambda s: "act" if s.get("last_error") and s.get("iteration", 0) < 2 else "report",
                                {"act": "act", "report": "report"})
        g.add_edge("report", END)
        return g.compile()

    # ---------------------------------------------------------- entrypoints
    async def run(self, task_id: str) -> None:
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if not task:
                log.error("task %s not found", task_id)
                return
            if task.status in ("completed", "cancelled"):
                return
            await self._apply_tenant_guards(db, task)
            state: AgentState = task.state or {}  # type: ignore[assignment]
            if not state.get("messages"):
                state = await self._init_state(db, task)
            else:
                # resumable state may be stale/corrupt — always guarantee a real workspace
                ws_path = await self._ensure_workspace(db, task)
                if not state.get("workspace") or not Path(state["workspace"]).is_dir():
                    state["workspace"] = str(ws_path)
            task.status = "running"
            task.attempts = (task.attempts or 0) + 1
            task.heartbeat_at = datetime.now(timezone.utc)
            await db.commit()
        await _emit(task_id, "task.status", {"status": "running"})

        try:
            result = await self.graph.ainvoke(state, {"recursion_limit": 200})
            await self._finalize(task_id, result)
        except TaskCancelled:
            await self._fail(task_id, "cancelled", "کار توسط کاربر لغو شد")
        except Exception as e:  # pragma: no cover - defensive
            log.exception("agent crashed for task %s", task_id)
            await self._fail(task_id, "failed", f"{type(e).__name__}: {e}")

    async def resume(self, task_id: str) -> None:
        """Resume a paused (approval) task."""
        await self.run(task_id)

    async def _init_state(self, db, task: Task) -> AgentState:
        # ensure workspace
        workspace_path = await self._ensure_workspace(db, task)
        # recall memories
        mem_text = ""
        try:
            items = await recall(db, user_id=task.user_id, query=task.instruction, project_id=task.project_id, limit=5)
            mem_text = format_memories(items)
        except Exception:
            log.warning("memory recall failed", exc_info=True)
        sys_prompt = SYSTEM_PROMPT.format(
            os=f"{__import__('platform').system()} {__import__('platform').release()}",
            workspace=str(workspace_path),
            today=datetime.now().strftime("%Y-%m-%d"),
        )
        if mem_text:
            sys_prompt += "\n\n" + mem_text
        messages = [{"role": "system", "content": sys_prompt}]
        # recent conversation history
        if task.conversation_id:
            rows = (await db.execute(
                select(Message).where(Message.conversation_id == task.conversation_id)
                .order_by(Message.created_at.desc()).limit(12)
            )).scalars().all()
            for m in reversed(rows):
                if m.role in ("user", "assistant") and m.content:
                    messages.append({"role": m.role, "content": m.content[:4000]})
        messages.append({"role": "user", "content": task.instruction})
        return AgentState(
            task_id=task.id, user_id=task.user_id, instruction=task.instruction,
            messages=messages, iteration=0, tool_count=0, pending_calls=[], paused=False,
            analysis={}, plan=[], final_text="", last_error="", workspace=str(workspace_path),
            project_id=task.project_id,
        )

    async def _ensure_workspace(self, db, task: Task) -> Path:
        if task.workspace_id:
            ws = (await db.execute(select(Workspace).where(Workspace.id == task.workspace_id))).scalar_one_or_none()
            if ws:
                Path(ws.path).mkdir(parents=True, exist_ok=True)
                return Path(ws.path)
        root = _settings.workspace_path / "workspaces" / f"task-{task.id[:8]}"
        root.mkdir(parents=True, exist_ok=True)
        ws = Workspace(user_id=task.user_id, project_id=task.project_id, name=f"task-{task.id[:8]}", path=str(root))
        db.add(ws)
        await db.commit()
        await db.refresh(ws)
        task.workspace_id = ws.id
        await db.commit()
        return root

    # ---------------------------------------------------------- nodes
    async def node_analyze(self, state: AgentState) -> AgentState:
        await self._check_cancel(state["task_id"])
        async with SessionLocal() as db:
            await self._add_step(db, state["task_id"], "analyze", "running", "تحلیل درخواست")
        analysis = {"kind": "chat", "risk": "safe", "summary": state["instruction"][:160],
                    "plan": ["اجرای درخواست", "بررسی نتیجه", "گزارش"], "needs_workspace": True}
        try:
            resp = await chat_resilient(
                self.provider,
                [{"role": "user", "content": PLANNER_PROMPT.format(instruction=state["instruction"][:3000])}],
                model=select_model("reason"), temperature=0.0, purpose="plan",
            )
            await self._track_usage(state, resp)
            text = (resp.content or "").strip()
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end + 1])
                analysis.update({k: parsed.get(k, analysis[k]) for k in analysis})
                if isinstance(parsed.get("plan"), list):
                    analysis["plan"] = [str(p)[:200] for p in parsed["plan"]][:8]
        except Exception:
            log.warning("planner LLM failed; using heuristic plan", exc_info=True)
        state["analysis"] = analysis
        async with SessionLocal() as db:
            await self._add_step(db, state["task_id"], "analyze", "ok",
                                 f"نوع: {analysis['kind']} | ریسک: {analysis['risk']}")
            task = (await db.execute(select(Task).where(Task.id == state["task_id"]))).scalar_one()
            task.kind = analysis.get("kind", "chat")
            task.risk = analysis.get("risk", "safe")
            await db.commit()
        await _emit(state["task_id"], "task.plan", {"plan": analysis.get("plan", [])})
        return state

    async def node_plan(self, state: AgentState) -> AgentState:
        plan = state.get("analysis", {}).get("plan") or ["اجرا", "بررسی", "گزارش"]
        state["plan"] = plan
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == state["task_id"]))).scalar_one()
            task.plan = [{"idx": i, "title": p, "status": "pending"} for i, p in enumerate(plan)]
            await db.commit()
            await self._add_step(db, state["task_id"], "plan", "ok", " | ".join(plan)[:500])
        return state

    async def node_act(self, state: AgentState) -> AgentState:
        await self._check_cancel(state["task_id"])

        # 1) execute any queued/pending calls first
        if state.get("pending_calls"):
            await self._execute_calls(state)
            if state.get("paused"):
                return state

        if state.get("iteration", 0) >= _settings.max_agent_iterations:
            state["last_error"] = "به سقف تعداد گام‌های اجرا رسیدیم"
            return state
        state["iteration"] = state.get("iteration", 0) + 1

        # 2) LLM turn with tools
        purpose = "code" if state.get("analysis", {}).get("kind") in ("project", "ops") else "chat"
        model = select_model(purpose)
        stream_buf: list[str] = []

        async def on_delta(chunk: str) -> None:
            stream_buf.append(chunk)
            await _emit(state["task_id"], "message.delta", {"delta": chunk})

        try:
            resp = await chat_resilient(
                self.provider, state["messages"], model=model, tools=registry.specs(),
                stream_cb=on_delta if not state.get("pending_calls") else None, purpose=purpose,
            )
        except Exception as e:
            state["last_error"] = f"LLM error: {e}"
            await _emit(state["task_id"], "task.warning", {"message": str(e)[:400]})
            return state

        await self._track_usage(state, resp)
        assistant_msg: dict = {"role": "assistant", "content": resp.content or ""}
        if resp.tool_calls:
            assistant_msg["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)}}
                for c in resp.tool_calls
            ]
        state["messages"] = state["messages"] + [assistant_msg]

        if resp.tool_calls:
            state["pending_calls"] = [
                {"id": c.id, "name": c.name, "arguments": c.arguments, "approved": False}
                for c in resp.tool_calls
            ]
            await self._execute_calls(state)
        else:
            state["final_text"] = resp.content or ""
            state["pending_calls"] = []
        return state

    async def _execute_calls(self, state: AgentState) -> None:
        calls = list(state.get("pending_calls") or [])
        state["pending_calls"] = []
        for call in calls:
            if state.get("tool_count", 0) >= _settings.max_tool_calls_per_task:
                state["messages"].append({
                    "role": "tool", "tool_call_id": call["id"], "name": call["name"],
                    "content": "⛔ سقف مجاز فراخوانی ابزار در این کار پر شده است.",
                })
                continue
            tool = registry.get(call["name"])
            if not tool:
                state["messages"].append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                                          "content": f"خطا: ابزار «{call['name']}» وجود ندارد. ابزارهای موجود: {[t.name for t in registry.all()]}"})
                continue
            risk = classify_risk(tool, call.get("arguments") or {})
            if risk == "blocked":
                await self._record_call(state, call, tool, risk, "blocked", 0)
                state["messages"].append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                                          "content": "⛔ این عملیات توسط سیاست امنیتی مسدود شد."})
                continue
            if risk in _settings.approval_levels and not call.get("approved"):
                await self._pause_for_approval(state, call, tool, risk, calls)
                return

            # execute
            started = time.monotonic()
            call_row_id = await self._record_call(state, call, tool, risk, "running", 0)
            await _emit(state["task_id"], "tool.start", {"tool": tool.name, "args": call.get("arguments"), "risk": risk})
            if not state.get("workspace"):
                state["messages"].append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                                          "content": "خطا: فضای‌کار تعیین نشده است؛ ابزار اجرا نشد."})
                continue
            ctx = ToolContext(
                user_id=state["user_id"], workspace_root=Path(state["workspace"]),
                task_id=state["task_id"], project_id=state.get("project_id"),
                timeout=_settings.exec_timeout_seconds,
            )
            try:
                result = await tool.run(call.get("arguments") or {}, ctx)
            except Exception as e:  # tool crash must not kill the task
                result = _TR(False, f"خطای ابزار: {type(e).__name__}: {e}")
            dur = int((time.monotonic() - started) * 1000)
            state["tool_count"] = state.get("tool_count", 0) + 1

            out = sanitize_output(result.output)[: _settings.max_output_bytes]
            async with SessionLocal() as db:
                db.add(ToolResult(tool_call_id=call_row_id, task_id=state["task_id"], ok=result.ok,
                                  output=out[:200_000], data=_jsonable(result.data) if isinstance(result.data, dict) else {}))
                row = (await db.execute(select(ToolCall).where(ToolCall.id == call_row_id))).scalar_one()
                row.status = "ok" if result.ok else "error"
                row.exit_code = result.exit_code
                row.duration_ms = dur
                row.finished_at = datetime.now(timezone.utc)
                await db.commit()
            state["messages"].append({"role": "tool", "tool_call_id": call["id"], "name": call["name"],
                                      "content": out[:20_000]})
            if not result.ok:
                state["last_error"] = out[:300]
            await _emit(state["task_id"], "tool.end", {
                "tool": tool.name, "ok": result.ok, "exit_code": result.exit_code,
                "duration_ms": dur, "output": out[:4000],
            })

    async def _record_call(self, state: AgentState, call: dict, tool, risk: str, status: str, dur: int) -> str:
        async with SessionLocal() as db:
            row = ToolCall(task_id=state["task_id"], tool_name=tool.name,
                           args=_jsonable(call.get("arguments") or {}), risk=risk, status=status,
                           started_at=datetime.now(timezone.utc), duration_ms=dur)
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return row.id

    async def _pause_for_approval(self, state: AgentState, call: dict, tool, risk: str, remaining: list[dict]) -> None:
        state["pending_calls"] = [call] + [c for c in remaining if c is not call]
        state["paused"] = True
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == state["task_id"]))).scalar_one()
            approval = Approval(
                task_id=task.id, user_id=state["user_id"], kind="tool",
                description=f"اجرای ابزار «{tool.name}» با ریسک {risk} نیازمند تأیید است",
                payload={"call": call, "risk": risk}, status="pending",
            )
            db.add(approval)
            task.status = "waiting_approval"
            task.state = _jsonable(state)  # type: ignore[assignment]
            await db.commit()
            await self._add_step(db, state["task_id"], "act", "skipped", f"در انتظار تأیید: {tool.name}")
        await _emit(state["task_id"], "approval.request", {
            "tool": tool.name, "risk": risk, "args": call.get("arguments"),
            "description": approval.description,
        })
        await _emit(state["task_id"], "task.status", {"status": "waiting_approval"})

    async def node_verify(self, state: AgentState) -> AgentState:
        await self._check_cancel(state["task_id"])
        tool_outputs = [m for m in state["messages"] if m.get("role") == "tool"]
        errors = [m for m in tool_outputs if "exit_code=0" not in (m.get("content") or "") and "exit_code" in (m.get("content") or "")]
        summary = "\n".join(f"- {m.get('name')}: {(m.get('content') or '')[:300]}" for m in tool_outputs[-8:])
        if errors and state.get("iteration", 0) <= 2:
            state["messages"].append({
                "role": "user",
                "content": "برخی اجراها خطا داشتند. علت را بررسی و اصلاح کن، سپس دوباره تست کن. اگر حل‌نشدنی است، صریح بگو.",
            })
            state["last_error"] = errors[-1].get("content", "error")
        else:
            state["last_error"] = ""
        async with SessionLocal() as db:
            await self._add_step(db, state["task_id"], "verify", "ok" if not state["last_error"] else "error",
                                 f"{len(tool_outputs)} ابزار اجرا شد" + ("" if not state["last_error"] else " | خطا باقی است"))
        state["verification"] = {"errors": len(errors), "tools": len(tool_outputs)}  # type: ignore[typeddict-unknown-key]
        return state

    async def node_report(self, state: AgentState) -> AgentState:
        final = state.get("final_text") or ""
        if not final:
            # one last LLM call without tools to write the report
            msgs = state["messages"] + [{
                "role": "user",
                "content": "اکنون گزارش نهایی فارسی بنویس: چه کاری انجام شد، فایل‌های کلیدی، نتیجه تست‌ها و موارد باقی‌مانده.",
            }]
            try:
                resp = await chat_resilient(self.provider, msgs, model=select_model("chat"), purpose="report")
                await self._track_usage(state, resp)
                final = resp.content.strip()
            except Exception as e:
                final = f"گزارش: اجرا با خطا مواجه شد ({e})."
        state["final_text"] = final
        async with SessionLocal() as db:
            await self._add_step(db, state["task_id"], "report", "ok", final[:500])
        return state

    # ---------------------------------------------------------- routing
    def _route_after_act(self, state: AgentState) -> str:
        if state.get("paused"):
            return "end"
        it = state.get("iteration", 0)
        if state.get("pending_calls"):
            return "act"
        # LLM finished its turn without tool calls → verify
        last = next((m for m in reversed(state.get("messages", [])) if m.get("role") == "assistant"), {})
        if last.get("tool_calls"):
            # we just executed tools; give the model another turn
            if it < _settings.max_agent_iterations:
                return "act"
        return "verify"

    # ---------------------------------------------------------- bookkeeping
    async def _check_cancel(self, task_id: str) -> None:
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if task and task.cancel_requested:
                raise TaskCancelled()

    async def _track_usage(self, state: AgentState, resp) -> None:
        usage = getattr(resp, "usage", None)
        if not usage:
            return
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == state["task_id"]))).scalar_one_or_none()
            if task:
                task.tokens_in += usage.tokens_in
                task.tokens_out += usage.tokens_out
                task.cost_usd += usage.cost_usd
            db.add(ModelUsage(user_id=state.get("user_id"), task_id=state["task_id"],
                              model=getattr(resp, "model", "") or select_model("chat"),
                              purpose="agent", tokens_in=usage.tokens_in,
                              tokens_out=usage.tokens_out, cost_usd=usage.cost_usd))
            await db.commit()

    async def _finalize(self, task_id: str, state: AgentState) -> None:
        paused = bool(state.get("paused"))
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if not task:
                return
            if paused:
                task.state = _jsonable({**state})  # type: ignore[assignment]
                await db.commit()
                return
            task.status = "completed"
            task.result = state.get("final_text", "")[:50_000]
            task.state = {}
            task.finished_at = datetime.now(timezone.utc)
            if task.conversation_id:
                db.add(Message(conversation_id=task.conversation_id, task_id=task.id, role="assistant",
                               content=task.result, meta={"kind": "final_report"}))
                conv = (await db.execute(select(Conversation).where(Conversation.id == task.conversation_id))).scalar_one_or_none()
                if conv and conv.title in ("گفت‌وگوی جدید", "", None):
                    conv.title = task.instruction[:60]
            await db.commit()
        await _emit(task_id, "task.done", {"status": "completed", "result": state.get("final_text", "")[:20000]})

    async def _fail(self, task_id: str, status: str, error: str) -> None:
        async with SessionLocal() as db:
            task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
            if not task:
                return
            task.status = status
            task.error = error[:5000]
            task.finished_at = datetime.now(timezone.utc)
            await db.commit()
            await self._add_step(db, task_id, "report", "error", error[:500])
        await _emit(task_id, "task.done", {"status": status, "error": error[:1000]})


_runner: AgentRunner | None = None


def get_runner() -> AgentRunner:
    global _runner
    if _runner is None:
        _runner = AgentRunner()
    return _runner
