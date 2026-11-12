"""Execution sandboxes: local (dev/test) and docker (prod, untrusted code)."""
from __future__ import annotations

import asyncio
import logging
import shlex
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings

log = logging.getLogger("sina.sandbox")


@dataclass
class ExecOutcome:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def merged(self, limit: int = 200_000) -> str:
        out = self.stdout[-limit:]
        err = self.stderr[-limit // 2:] if self.stderr else ""
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append("--- stderr ---\n" + err)
        if self.timed_out:
            parts.append("⏱ TIMEOUT: process exceeded the time limit and was killed.")
        body = "\n".join(parts) if parts else "(no output)"
        return f"{body}\n[exit_code={self.exit_code}]"


class LocalSandbox:
    """Runs commands on the host inside the workspace dir.

    Suitable for the dev/test environment. NEVER expose the API publicly with this
    mode: production uses DockerSandbox (unprivileged, no-net, read-only rootfs).
    """

    mode = "local"

    def __init__(self, timeout: int = 120) -> None:
        self.timeout = timeout

    async def exec(self, command: str, cwd: Path, timeout: int | None = None,
                   env: dict[str, str] | None = None) -> ExecOutcome:
        import os
        timeout = timeout or self.timeout
        full_env = {**os.environ, "PYTHONUNBUFFERED": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
        full_env.update(env or {})
        proc = await asyncio.create_subprocess_shell(
            command, cwd=str(cwd), env=full_env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout)
            return ExecOutcome(proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace"))
        except asyncio.TimeoutError:
            try:
                import os, signal
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            out, err = await proc.communicate()
            return ExecOutcome(124, out.decode(errors="replace"), err.decode(errors="replace"), timed_out=True)


class DockerSandbox:
    """Runs code in ephemeral hardened containers.

    Hardening: no network by default, non-root user, read-only rootfs + tmpfs,
    memory/pids/cpu limits, cap-drop ALL, no-new-privileges, workspace bind mount.
    """

    mode = "docker"

    def __init__(self, image: str = "python:3.12-slim", network: str = "none", timeout: int = 120) -> None:
        self.image = image
        self.network = network
        self.timeout = timeout

    async def exec(self, command: str, cwd: Path, timeout: int | None = None,
                   env: dict[str, str] | None = None) -> ExecOutcome:
        s = get_settings()
        timeout = timeout or self.timeout
        args = [
            "docker", "run", "--rm",
            "--network", self.network,
            "--memory", "512m", "--memory-swap", "512m",
            "--cpus", "1.0", "--pids-limit", "128",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m",
            "-v", f"{cwd}:/workspace:rw",
            "-w", "/workspace",
            "--user", "1000:1000",
        ]
        for k, v in (env or {}).items():
            args += ["-e", f"{k}={v}"]
        args += [self.image, "sh", "-lc", command]
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout + 10)
            return ExecOutcome(proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace"))
        except asyncio.TimeoutError:
            proc.kill()
            out, err = await proc.communicate()
            return ExecOutcome(124, out.decode(errors="replace"), err.decode(errors="replace"), timed_out=True)


def get_sandbox(mode: str | None = None):
    s = get_settings()
    mode = mode or ("docker" if s.env == "prod" else "local")
    if mode == "docker":
        return DockerSandbox(timeout=s.exec_timeout_seconds)
    return LocalSandbox(timeout=s.exec_timeout_seconds)
