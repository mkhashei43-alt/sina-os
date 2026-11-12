"""Workspaces + file explorer + manual terminal (real file ops, path-safe)."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..deps import get_current_user
from ..models import User, Workspace
from ..security import UnsafePathError, safe_join, sanitize_output
from ..services.sandbox import get_sandbox
from ..tools.base import classify_command

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
uploads_router = APIRouter(prefix="/uploads", tags=["uploads"])
_settings = get_settings()


async def _get_ws(db: AsyncSession, user: User, ws_id: str) -> Workspace:
    ws = (await db.execute(select(Workspace).where(Workspace.id == ws_id, Workspace.user_id == user.id))).scalar_one_or_none()
    if not ws or ws.status == "deleted":
        raise HTTPException(404, "فضای‌کار یافت نشد")
    return ws


@router.get("")
async def list_workspaces(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = (await db.execute(select(Workspace).where(Workspace.user_id == user.id, Workspace.status != "deleted")
                             .order_by(Workspace.created_at.desc()))).scalars().all()
    out = []
    for w in rows:
        p = Path(w.path)
        files = sum(1 for f in p.rglob("*") if f.is_file()) if p.exists() else 0
        out.append({"id": w.id, "name": w.name, "path": w.path, "status": w.status,
                    "project_id": w.project_id, "files": files, "created_at": w.created_at})
    return out


class WsIn(BaseModel):
    name: str
    project_id: str | None = None


@router.post("")
async def create_workspace(body: WsIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    safe_name = "".join(c for c in body.name if c.isalnum() or c in "-_").strip() or "workspace"
    path = _settings.workspace_path / "workspaces" / f"{safe_name}-{user.id[:4]}"
    path.mkdir(parents=True, exist_ok=True)
    ws = Workspace(user_id=user.id, name=body.name, path=str(path), project_id=body.project_id)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return {"id": ws.id, "name": ws.name, "path": ws.path}


@router.delete("/{ws_id}")
async def delete_workspace(ws_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    p = Path(ws.path).resolve()
    root = _settings.workspace_path.resolve()
    if root not in p.parents:
        raise HTTPException(400, "مسیر خارج از ریشه مجاز است")
    shutil.rmtree(p, ignore_errors=True)
    ws.status = "deleted"
    await db.commit()
    return {"ok": True}


@router.get("/{ws_id}/files")
async def list_files(ws_id: str, path: str = ".", user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    try:
        base = safe_join(Path(ws.path), path)
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    if not base.exists():
        raise HTTPException(404, "مسیر یافت نشد")
    entries = []
    for p in sorted(base.iterdir()):
        if p.name in (".git", "node_modules", "__pycache__"):
            continue
        st = p.stat()
        entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file",
                        "size": st.st_size, "modified": st.st_mtime,
                        "path": str(p.relative_to(Path(ws.path)))})
    return {"path": path, "entries": entries}


@router.get("/{ws_id}/file")
async def read_file(ws_id: str, path: str = Query(...), download: bool = False,
                    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    try:
        p = safe_join(Path(ws.path), path)
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    if not p.is_file():
        raise HTTPException(404, "فایل یافت نشد")
    if download:
        return FileResponse(p, filename=p.name)
    size = p.stat().st_size
    if size > 1_000_000:
        raise HTTPException(413, "فایل بزرگ است؛ از دانلود استفاده کنید")
    try:
        content = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(415, "فایل متنی نیست")
    return {"path": path, "size": size, "content": content}


@router.post("/{ws_id}/upload")
async def upload(ws_id: str, path: str = ".", file: UploadFile = File(...),
                 user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    data = await file.read()
    if len(data) > _settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"حجم فایل بیش از {_settings.max_upload_mb}MB است")
    name = Path(file.filename or "upload.bin").name  # strip any directory parts
    try:
        dest = safe_join(Path(ws.path), str(Path(path) / name))
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"ok": True, "path": str(dest.relative_to(Path(ws.path))), "bytes": len(data)}


class MkdirIn(BaseModel):
    path: str


@router.post("/{ws_id}/mkdir")
async def mkdir(ws_id: str, body: MkdirIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    try:
        p = safe_join(Path(ws.path), body.path)
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    p.mkdir(parents=True, exist_ok=True)
    return {"ok": True}


@router.delete("/{ws_id}/file")
async def delete_file(ws_id: str, path: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    ws = await _get_ws(db, user, ws_id)
    try:
        p = safe_join(Path(ws.path), path)
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    if p == Path(ws.path).resolve():
        raise HTTPException(400, "حذف ریشه مجاز نیست")
    if p.is_dir():
        shutil.rmtree(p)
    elif p.exists():
        p.unlink()
    else:
        raise HTTPException(404, "مسیر یافت نشد")
    return {"ok": True}


class ExecIn(BaseModel):
    command: str
    cwd: str = "."
    timeout: int = 60


@router.post("/{ws_id}/exec")
async def exec_command(ws_id: str, body: ExecIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    from ..deps import require_roles  # noqa: F401  (role gate documented below)
    if user.role not in ("owner", "admin"):
        raise HTTPException(403, "اجرای دستور فقط برای نقش owner/admin مجاز است")
    ws = await _get_ws(db, user, ws_id)
    risk = classify_command(body.command)
    if risk == "blocked":
        raise HTTPException(403, "این دستور مسدود است")
    try:
        cwd = safe_join(Path(ws.path), body.cwd)
    except UnsafePathError as e:
        raise HTTPException(400, str(e))
    timeout = min(max(body.timeout, 1), _settings.exec_timeout_seconds)
    outcome = await get_sandbox().exec(body.command, cwd, timeout)
    return {"exit_code": outcome.exit_code, "timed_out": outcome.timed_out,
            "output": sanitize_output(outcome.merged(_settings.max_output_bytes)), "risk": risk}


@uploads_router.post("")
async def upload_attachment(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """Store a chat attachment in the uploads area and return its path."""
    import uuid as _uuid
    data = await file.read()
    if len(data) > _settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"حجم فایل بیش از {_settings.max_upload_mb}MB است")
    name = Path(file.filename or "file.bin").name
    folder = _settings.workspace_path / "uploads" / user.id[:8]
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{_uuid.uuid4().hex[:8]}-{name}"
    dest.write_bytes(data)
    return {"ok": True, "path": str(dest), "name": name, "bytes": len(data)}
