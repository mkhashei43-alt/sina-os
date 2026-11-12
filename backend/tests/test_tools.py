"""Tool execution tests against a real temp workspace."""
from __future__ import annotations

import pytest

from app.tools import ToolContext, registry


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(user_id="u1", workspace_root=tmp_path, timeout=30)


async def test_files_write_read_search(ctx):
    files = registry.get("files")
    r = await files.run({"operation": "write", "path": "src/a.py", "content": "print('hi')"}, ctx)
    assert r.ok and (ctx.workspace_root / "src/a.py").exists()
    r = await files.run({"operation": "read", "path": "src/a.py"}, ctx)
    assert r.ok and "print" in r.output
    r = await files.run({"operation": "search", "pattern": "print"}, ctx)
    assert r.ok and "src/a.py" in r.output
    r = await files.run({"operation": "read", "path": "../../etc/passwd"}, ctx)
    assert not r.ok


async def test_files_delete_and_list(ctx):
    files = registry.get("files")
    await files.run({"operation": "mkdir", "path": "d1"}, ctx)
    await files.run({"operation": "write", "path": "d1/x.txt", "content": "x"}, ctx)
    r = await files.run({"operation": "list"}, ctx)
    assert "d1/x.txt" in r.output
    r = await files.run({"operation": "delete", "path": "d1"}, ctx)
    assert r.ok and not (ctx.workspace_root / "d1").exists()


async def test_terminal_exec_real(ctx):
    term = registry.get("terminal")
    r = await term.run({"command": "echo sina-ok && pwd"}, ctx)
    assert r.ok and "sina-ok" in r.output and r.exit_code == 0


async def test_terminal_nonzero_exit(ctx):
    term = registry.get("terminal")
    r = await term.run({"command": "exit 3"}, ctx)
    assert not r.ok and r.exit_code == 3


async def test_terminal_blocks_dangerous(ctx):
    term = registry.get("terminal")
    r = await term.run({"command": "sudo rm -rf /"}, ctx)
    assert not r.ok and "مسدود" in r.output


async def test_terminal_timeout(ctx):
    term = registry.get("terminal")
    r = await term.run({"command": "sleep 5", "timeout": 1}, ctx)
    assert not r.ok and "TIMEOUT" in r.output


async def test_python_exec(ctx):
    py = registry.get("python_exec")
    r = await py.run({"operation": "run", "code": "print(2+2)"}, ctx)
    assert r.ok and "4" in r.output


async def test_python_install_allowlist(ctx):
    py = registry.get("python_exec")
    r = await py.run({"operation": "install", "packages": ["definitely-not-allowed-pkg"]}, ctx)
    assert not r.ok and "مجاز نیست" in r.output


async def test_workspace_and_monitor(ctx):
    ws = registry.get("workspace")
    r = await ws.run({"operation": "info"}, ctx)
    assert r.ok
    mon = registry.get("system_monitor")
    r = await mon.run({"detail": "summary"}, ctx)
    assert r.ok and "cpu" in r.output


async def test_web_fetch_extracts_text(ctx):
    web = registry.get("web_fetch")
    r = await web.run({"url": "https://example.com"}, ctx)
    if not r.ok:  # offline CI is acceptable; must fail clearly
        assert "ناموفق" in r.output or "خطا" in r.output
    else:
        assert "Example" in r.output


async def test_unknown_tool_absent():
    assert registry.get("does_not_exist") is None
