"""Workspace Manager + System Monitor tools."""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import psutil

from ..config import get_settings
from .base import Tool, ToolContext, ToolResult, registry


class WorkspaceTool(Tool):
    name = "workspace"
    risk = "safe"
    description = "Manage the task workspace: info (size, path, file count), tree (project structure), clean_temp (remove __pycache__/temp files), snapshot (copy workspace into artifacts archive)."
    parameters = {
        "type": "object",
        "properties": {"operation": {"type": "string", "enum": ["info", "tree", "clean_temp", "snapshot"]}},
        "required": ["operation"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        op = args["operation"]
        root = ctx.workspace_root
        if op == "info":
            files = [p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
            size = sum(p.stat().st_size for p in files)
            return ToolResult(True, f"workspace: {root}\nfiles: {len(files)}\nsize: {size / 1024:.1f} KB", {"files": len(files), "bytes": size})
        if op == "tree":
            out = subprocess.run(["find", ".", "-maxdepth", "3", "-not", "-path", "*/.git/*", "-not", "-path", "*/node_modules/*"],
                                 cwd=root, capture_output=True, text=True, timeout=20).stdout
            return ToolResult(True, out[:8000] or "(empty workspace)")
        if op == "clean_temp":
            removed = 0
            for p in list(root.rglob("__pycache__")) + list(root.rglob("*.pyc")):
                try:
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
                    removed += 1
                except OSError:
                    pass
            return ToolResult(True, f"پاک‌سازی انجام شد ({removed} مورد)")
        if op == "snapshot":
            s = get_settings()
            dest = s.workspace_path / "artifacts" / f"ws-{ctx.task_id or 'manual'}.tar.gz"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.make_archive(str(dest)[: -7], "gztar", root_dir=root)
            return ToolResult(True, f"اسنپ‌شات: {dest}", {"path": str(dest)})
        return ToolResult(False, "عملیات ناشناخته")


class SystemMonitorTool(Tool):
    name = "system_monitor"
    risk = "safe"
    description = "Report host health: CPU, memory, disk, load, top processes, listening ports, and health of local services (postgres/redis ports). Read-only."
    parameters = {"type": "object", "properties": {"detail": {"type": "string", "enum": ["summary", "processes", "ports", "all"], "default": "summary"}}}

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        detail = args.get("detail", "summary")
        lines: list[str] = []
        if detail in ("summary", "all"):
            lines += [
                f"host: {socket.gethostname()}",
                f"cpu: {psutil.cpu_percent(interval=0.3):.1f}% ({psutil.cpu_count()} cores)",
                f"load: {os.getloadavg()}",
                f"ram: {psutil.virtual_memory().percent}% used of {psutil.virtual_memory().total // 2**30} GiB",
                f"disk: {psutil.disk_usage('/').percent}% of {psutil.disk_usage('/').total // 2**30} GiB",
            ]
        if detail in ("processes", "all"):
            procs = sorted(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
                           key=lambda p: p.info.get("cpu_percent") or 0, reverse=True)[:10]
            lines.append("top processes:")
            lines += [f"  {p.info['pid']:>6} {p.info['name'][:30]:<30} cpu={p.info['cpu_percent']:.1f}% mem={p.info['memory_percent']:.1f}%" for p in procs]
        if detail in ("ports", "all"):
            try:
                conns = psutil.net_connections(kind="inet")
                listening = sorted({c.laddr.port for c in conns if c.status == psutil.CONN_LISTEN})
                lines.append(f"listening ports: {listening[:40]}")
            except (psutil.AccessDenied, PermissionError):
                lines.append("listening ports: (permission denied)")
        return ToolResult(True, "\n".join(lines))


registry.register(WorkspaceTool())
registry.register(SystemMonitorTool())
