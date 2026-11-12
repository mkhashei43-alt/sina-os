"""Terminal tool — sandboxed bash execution with risk classification."""
from __future__ import annotations

from ..config import get_settings
from ..security import sanitize_output
from ..services.sandbox import get_sandbox
from .base import Tool, ToolContext, ToolResult, classify_command, registry


class TerminalTool(Tool):
    name = "terminal"
    risk = "safe"  # elevated dynamically by classify_command
    description = (
        "Execute shell commands inside an isolated sandbox rooted at the workspace. "
        "Use for: creating projects, installing allow-listed pip packages, running scripts, git, npm. "
        "Commands like rm -rf /, sudo, shutdown, iptables are blocked. Returns stdout, stderr and exit code."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "bash command"},
            "cwd": {"type": "string", "description": "relative working dir (default workspace root)"},
            "timeout": {"type": "integer", "description": "seconds (max configured limit)"},
        },
        "required": ["command"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        command = (args.get("command") or "").strip()
        if not command:
            return ToolResult(False, "دستور خالی است")
        risk = classify_command(command)
        if risk == "blocked":
            return ToolResult(False, "⛔ این دستور به دلایل امنیتی مسدود است و اجرا نشد.")
        s = get_settings()
        from ..security import safe_join, UnsafePathError
        try:
            cwd = safe_join(ctx.workspace_root, args.get("cwd") or ".")
        except UnsafePathError as e:
            return ToolResult(False, f"مسیر نامعتبر: {e}")
        cwd.mkdir(parents=True, exist_ok=True)
        timeout = min(int(args.get("timeout") or ctx.timeout), s.exec_timeout_seconds)
        sandbox = get_sandbox(ctx.exec_mode)
        outcome = await sandbox.exec(command, cwd, timeout)
        out = sanitize_output(outcome.merged(s.max_output_bytes))
        return ToolResult(outcome.exit_code == 0, out, {"mode": sandbox.mode, "timed_out": outcome.timed_out}, outcome.exit_code)


class PythonTool(Tool):
    name = "python_exec"
    risk = "safe"
    description = (
        "Run a Python script inside the workspace (or inspect it). Operations: run (write code to a temp file and execute), "
        "run_file (execute an existing .py file), install (pip install allow-listed packages). "
        "Returns stdout/stderr/exit code."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["run", "run_file", "install"], "default": "run"},
            "code": {"type": "string", "description": "python source (operation=run)"},
            "path": {"type": "string", "description": "existing file path (run_file)"},
            "packages": {"type": "array", "items": {"type": "string"}, "description": "packages for install"},
            "timeout": {"type": "integer"},
        },
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        op = args.get("operation", "run")
        s = get_settings()
        sandbox = get_sandbox(ctx.exec_mode)
        timeout = min(int(args.get("timeout") or ctx.timeout), s.exec_timeout_seconds)
        if op == "install":
            pkgs = [p for p in (args.get("packages") or []) if p]
            denied = [p for p in pkgs if p.split("==")[0].split(">=")[0].lower() not in s.pip_allow]
            if denied:
                return ToolResult(False, f"⛔ نصب این بسته‌ها مجاز نیست: {', '.join(denied)} (allow-list در تنظیمات)")
            cmd = "pip install --no-input " + " ".join(pkgs)
            outcome = await sandbox.exec(cmd, ctx.workspace_root, timeout)
            return ToolResult(outcome.exit_code == 0, outcome.merged(20_000), exit_code=outcome.exit_code)
        if op == "run_file":
            path = args.get("path", "")
            cmd = f"python3 {path}"
        else:
            code = args.get("code", "")
            if not code.strip():
                return ToolResult(False, "کدی ارائه نشده است")
            tmp = ctx.workspace_root / ".sina_tmp_run.py"
            tmp.write_text(code, encoding="utf-8")
            cmd = "python3 .sina_tmp_run.py"
        outcome = await sandbox.exec(cmd, ctx.workspace_root, timeout)
        out = sanitize_output(outcome.merged(s.max_output_bytes))
        return ToolResult(outcome.exit_code == 0, out, {"mode": sandbox.mode, "timed_out": outcome.timed_out}, outcome.exit_code)


registry.register(TerminalTool())
registry.register(PythonTool())
