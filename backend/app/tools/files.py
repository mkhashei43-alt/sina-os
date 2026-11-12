"""File Manager tool — path-safe CRUD inside the task workspace."""
from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path

from ..security import UnsafePathError, safe_join
from .base import Tool, ToolContext, ToolResult, registry

MAX_READ = 200_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}


class FilesTool(Tool):
    name = "files"
    risk = "safe"
    description = (
        "Manage files inside the isolated workspace. Operations: write (create/overwrite a file), "
        "read, append, delete, mkdir, list (tree), move, copy, search (glob or content grep), stat. "
        "All paths are relative to the workspace root."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["write", "read", "append", "delete", "mkdir", "list", "move", "copy", "search", "stat"]},
            "path": {"type": "string", "description": "relative path, e.g. 'app/main.py'"},
            "content": {"type": "string", "description": "file content for write/append"},
            "dest": {"type": "string", "description": "destination for move/copy"},
            "pattern": {"type": "string", "description": "glob or text to search for (search op)"},
            "recursive": {"type": "boolean", "default": True},
            "destructive": {"type": "boolean", "description": "set true for mass deletes"},
        },
        "required": ["operation"],
    }

    async def run(self, args: dict, ctx: ToolContext) -> ToolResult:
        op = args.get("operation")
        try:
            if op == "write":
                p = safe_join(ctx.workspace_root, args["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                content = args.get("content", "")
                p.write_text(content, encoding="utf-8")
                return ToolResult(True, f"نوشته شد: {args['path']} ({len(content)} bytes)", {"path": args["path"], "bytes": len(content)})
            if op == "append":
                p = safe_join(ctx.workspace_root, args["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a", encoding="utf-8") as f:
                    f.write(args.get("content", ""))
                return ToolResult(True, f"افزوده شد: {args['path']}", {"path": args["path"]})
            if op == "read":
                p = safe_join(ctx.workspace_root, args["path"])
                if not p.is_file():
                    return ToolResult(False, f"فایل یافت نشد: {args['path']}")
                data = p.read_text(encoding="utf-8", errors="replace")[:MAX_READ]
                return ToolResult(True, data, {"path": args["path"], "truncated": len(data) >= MAX_READ})
            if op == "delete":
                p = safe_join(ctx.workspace_root, args["path"])
                if p == ctx.workspace_root.resolve():
                    return ToolResult(False, "حذف ریشه فضای‌کار مجاز نیست")
                if p.is_dir():
                    shutil.rmtree(p)
                elif p.exists():
                    p.unlink()
                else:
                    return ToolResult(False, f"مسیر یافت نشد: {args['path']}")
                return ToolResult(True, f"حذف شد: {args['path']}", {"path": args["path"]})
            if op == "mkdir":
                p = safe_join(ctx.workspace_root, args["path"])
                p.mkdir(parents=True, exist_ok=True)
                return ToolResult(True, f"پوشه ساخته شد: {args['path']}", {"path": args["path"]})
            if op == "list":
                root = safe_join(ctx.workspace_root, args.get("path", "."))
                if not root.exists():
                    return ToolResult(False, f"مسیر یافت نشد: {args.get('path')}")
                lines: list[str] = []
                files = 0
                for p in sorted(root.rglob("*") if args.get("recursive", True) else root.iterdir()):
                    rel = p.relative_to(ctx.workspace_root)
                    if any(part in SKIP_DIRS for part in rel.parts):
                        continue
                    if p.is_dir():
                        lines.append(f"{rel}/")
                    else:
                        files += 1
                        lines.append(f"{rel}  ({p.stat().st_size}b)")
                    if len(lines) >= 500:
                        lines.append("... (truncated)")
                        break
                return ToolResult(True, "\n".join(lines) or "(empty)", {"count": files})
            if op in ("move", "copy"):
                src = safe_join(ctx.workspace_root, args["path"])
                dst = safe_join(ctx.workspace_root, args["dest"])
                if not src.exists():
                    return ToolResult(False, f"مبدأ یافت نشد: {args['path']}")
                dst.parent.mkdir(parents=True, exist_ok=True)
                (shutil.move if op == "move" else shutil.copytree if src.is_dir() else shutil.copy2)(str(src), str(dst))
                return ToolResult(True, f"{op} انجام شد: {args['path']} → {args['dest']}")
            if op == "search":
                root = safe_join(ctx.workspace_root, args.get("path", "."))
                pattern = args.get("pattern", "*")
                hits: list[str] = []
                grep = not any(ch in pattern for ch in "*?[")
                for p in root.rglob("*"):
                    if p.is_dir() or any(part in SKIP_DIRS for part in p.relative_to(ctx.workspace_root).parts):
                        continue
                    rel = str(p.relative_to(ctx.workspace_root))
                    if grep:
                        try:
                            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                                if pattern in line:
                                    hits.append(f"{rel}:{i}: {line[:200]}")
                                    break
                        except OSError:
                            continue
                    elif fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(p.name, pattern):
                        hits.append(rel)
                    if len(hits) >= 200:
                        break
                return ToolResult(True, "\n".join(hits) or "نتیجه‌ای یافت نشد", {"count": len(hits)})
            if op == "stat":
                p = safe_join(ctx.workspace_root, args["path"])
                if not p.exists():
                    return ToolResult(False, f"مسیر یافت نشد: {args['path']}")
                st = p.stat()
                return ToolResult(True, f"{args['path']}: {'dir' if p.is_dir() else 'file'}, {st.st_size} bytes", {"size": st.st_size, "is_dir": p.is_dir()})
            return ToolResult(False, f"عملیات ناشناخته: {op}")
        except UnsafePathError as e:
            return ToolResult(False, f"خطای امنیتی مسیر: {e}")
        except Exception as e:
            return ToolResult(False, f"خطای فایل: {type(e).__name__}: {e}")


registry.register(FilesTool())
