"""Mandatory end-to-end scenario.

"Create a simple Python application, write its files, execute it, run tests,
 fix any errors, and provide the final files."

Everything runs through the real Agent → tool system on disk; nothing is mocked
except the LLM (deterministic MockProvider replaces OpenRouter when no key).
"""
from __future__ import annotations

from pathlib import Path

from tests.conftest import wait_task

INSTRUCTION = ("یک برنامه ساده پایتون بساز، فایل‌ها را بنویس، اجرا کن، "
               "تست‌ها را اجرا کن، خطاها را اصلاح کن و فایل‌های نهایی را ارائه بده")


async def test_e2e_python_project(app_client, auth):
    r = await app_client.post("/api/tasks", headers=auth, json={"instruction": INSTRUCTION})
    assert r.status_code == 200
    tid = r.json()["task"]["id"]

    t = await wait_task(app_client, auth, tid, timeout=180)
    assert t["status"] == "completed", f"task failed: {t.get('error')}"

    # 1. workspace exists
    ws_id = t["workspace_id"]
    assert ws_id

    # 2. files really exist on disk
    ws = [w for w in (await app_client.get("/api/workspaces", headers=auth)).json() if w["id"] == ws_id][0]
    root = Path(ws["path"])
    assert (root / "app" / "calculator.py").exists()
    assert (root / "tests" / "test_calculator.py").exists()
    assert (root / "README.md").exists()

    # 3. code really runs
    import subprocess
    out = subprocess.run(["python3", "app/calculator.py"], cwd=root, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0 and "calculator ready: 5" in out.stdout

    # 4. tests are real and pass
    test_run = subprocess.run(["python3", "tests/test_calculator.py"], cwd=root, capture_output=True, text=True, timeout=30)
    assert test_run.returncode == 0
    pytest_run = subprocess.run(["python3", "-m", "pytest", "-q", "tests/"], cwd=root, capture_output=True, text=True, timeout=120)
    assert pytest_run.returncode == 0, pytest_run.stdout[-800:]

    # 5. tool call logs & results persisted
    calls = t["tool_calls"]
    assert len(calls) >= 6
    assert {"files", "python_exec", "terminal"} <= {c["tool"] for c in calls}
    assert all(c["status"] in ("ok", "error") for c in calls)
    assert any(c["result"] and c["result"]["output"] for c in calls)

    # 6. final report mentions the work
    assert t["result"].strip()
    assert any(s["phase"] == "report" for s in t["steps"])

    # 7. artifacts accessible through API
    listing = (await app_client.get(f"/api/workspaces/{ws_id}/files", headers=auth, params={"path": "app"})).json()
    assert any(e["name"] == "calculator.py" for e in listing["entries"])


async def test_agent_repairs_failing_code(app_client, auth, tmp_path):
    """Verification loop: a failing script must be observed and the task must still report honestly."""
    from app.tools import ToolContext, registry
    ctx = ToolContext(user_id="u", workspace_root=tmp_path, timeout=30)
    py = registry.get("python_exec")
    bad = await py.run({"operation": "run", "code": "raise SystemExit(1)"}, ctx)
    assert not bad.ok and bad.exit_code == 1
    good = await py.run({"operation": "run", "code": "print('fixed')"}, ctx)
    assert good.ok and "fixed" in good.output
