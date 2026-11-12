"""Tool system: base contracts + risk classification + registry."""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

RISK_RANK = {"safe": 0, "confirm": 1, "admin": 2}


@dataclass
class ToolContext:
    user_id: str
    workspace_root: Path          # isolated directory for this task
    task_id: str | None = None
    project_id: str | None = None
    timeout: int = 120
    exec_mode: str = "local"      # local | docker
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)
    exit_code: int | None = None

    def as_text(self) -> str:
        return self.output if self.output else ("OK" if self.ok else "ERROR")


class Tool:
    name: str = ""
    description: str = ""
    risk: str = "safe"
    parameters: dict = {}

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:  # pragma: no cover
        raise NotImplementedError

    def risk_for(self, args: dict) -> str:
        """ریسک واقعیِ این فراخوانی (ابزارهای شبکه‌ای بر اساس متد تصمیم می‌گیرند)."""
        return self.risk

    def spec(self) -> dict:
        """OpenAI-style function spec for LLM tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._hooks: list[Callable[..., Awaitable[None]]] = []

    def register(self, tool: Tool) -> None:
        if not tool.name:
            raise ValueError("tool needs a name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self, allow: set[str] | None = None) -> list[dict]:
        return [t.spec() for t in self._tools.values() if not allow or t.name in allow]


registry = ToolRegistry()


# ---------------- risk classification ----------------
_BLOCKED_PATTERNS = [
    r"\bmkfs(\.\w+)?\b", r"\bdd\s+if=.*of=/dev/", r":\(\)\s*\{\s*:\|:&\s*\};:",
    r"\b(shutdown|reboot|poweroff|halt)\b", r"\bsudo\b", r"\bsu\s+-",
    r"\biptables\b", r"\bnft\b", r"\bufw\b",
    r"rm\s+(-\w*\s+)*(/|/\*|~|\$HOME)(\s|$)",
    r">\s*/dev/sd[a-z]", r"\bchown\s+-R\s+root", r"\bpasswd\b",
    r"curl[^|]*\|\s*(ba)?sh", r"wget[^|]*\|\s*(ba)?sh",
    r"docker\s+(run|exec)?.*--privileged", r"/var/run/docker\.sock",
]
_ADMIN_PATTERNS = [
    r"\bsystemctl\b", r"\bservice\s+\w+\s+(start|stop|restart)", r"\bapt(-get)?\s+(install|remove|purge)",
    r"\bnpm\s+(install|i)\s+-g\b", r"\bcrontab\b", r"\bhistory\s+-c\b",
    r"\bgit\s+push\b.*--force", r"\bgit\s+reset\s+--hard\b",
]
_CONFIRM_PATTERNS = [
    r"\brm\s+-", r"\bmv\s+.*\s+/(etc|usr|var|opt)\b", r"\bgit\s+push\b",
    r"\bdocker\s+(rm|rmi|stop|kill)\b", r"\bkill(all)?\s+", r"\btruncate\b",
    r"\bnc\s+", r"\bsocat\b", r"\bssh\b",
]


_PIP_INSTALL_RE = re.compile(r"\bpip3?\s+install\b(.*)")


def _pip_is_allowlisted(command: str, allow: set[str]) -> bool:
    from ..config import get_settings
    allow = allow or get_settings().pip_allow
    m = _PIP_INSTALL_RE.search(command)
    if not m:
        return False
    tokens = [t for t in m.group(1).split() if not t.startswith("-")]
    pkgs = {re.split(r"[<>=!~\[;]", t)[0].strip().lower() for t in tokens if t not in (".", "-e")}
    return bool(pkgs) and pkgs <= allow


def classify_command(command: str, pip_allow: set[str] | None = None) -> str:
    """Return risk level: safe | confirm | admin | blocked."""
    for pat in _BLOCKED_PATTERNS:
        if re.search(pat, command):
            return "blocked"
    if _PIP_INSTALL_RE.search(command) and "uninstall" not in command:
        # allow-listed libraries are safe inside the sandbox; anything else needs a human
        return "safe" if _pip_is_allowlisted(command, pip_allow or set()) else "admin"
    for pat in _ADMIN_PATTERNS:
        if re.search(pat, command):
            return "admin"
    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, command):
            return "confirm"
    return "safe"


def classify_risk(tool: Tool, args: dict) -> str:
    """Effective risk of a concrete call."""
    try:
        risk = tool.risk_for(args)
    except Exception:
        risk = tool.risk
    cmd = args.get("command") or args.get("code") or ""
    if tool.name in ("terminal", "python_exec") and isinstance(cmd, str):
        cmd_risk = classify_command(cmd)
        if cmd_risk == "blocked":
            return "blocked"
        if RISK_RANK.get(cmd_risk, 0) > RISK_RANK.get(risk, 0):
            risk = cmd_risk
    if tool.name == "files" and args.get("operation") in ("delete", "move", "write") and args.get("destructive"):
        risk = max(risk, "confirm", key=lambda r: RISK_RANK.get(r, 0))
    return risk
