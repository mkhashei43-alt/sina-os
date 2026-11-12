"use client";
import { useEffect, useState } from "react";
import { api, fmtBytes, fmtDate } from "@/lib/api";
import { Card, Code, Empty, SectionTitle, Spinner } from "@/components/ui";

export default function FilesPage() {
  const [wss, setWss] = useState<any[]>([]);
  const [ws, setWs] = useState<any>(null);
  const [path, setPath] = useState(".");
  const [entries, setEntries] = useState<any[]>([]);
  const [file, setFile] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    const qs = new URLSearchParams(location.search).get("ws");
    api<any[]>("/workspaces").then((list) => {
      setWss(list);
      const chosen = list.find((w) => w.id === qs) || list[0];
      if (chosen) { setWs(chosen); browse(chosen.id, "."); }
    });
  }, []);

  async function browse(wsId: string, p: string) {
    setBusy(true); setPath(p);
    try {
      const d = await api(`/workspaces/${wsId}/files?path=${encodeURIComponent(p)}`);
      setEntries(d.entries || []);
    } finally { setBusy(false); }
  }

  async function openFile(e: any) {
    if (e.type === "dir") { browse(ws.id, e.path); return; }
    try {
      const d = await api(`/workspaces/${ws.id}/file?path=${encodeURIComponent(e.path)}`);
      setFile(d);
    } catch (err: any) { setFile({ path: e.path, content: err.message }); }
  }

  async function mkdir() {
    if (!newName.trim()) return;
    await api(`/workspaces/${ws.id}/mkdir`, { method: "POST", body: JSON.stringify({ path: `${path}/${newName}`.replace("./", "") }) });
    setNewName(""); browse(ws.id, path);
  }

  async function upload(f: File) {
    setUploading(true);
    const fd = new FormData(); fd.append("file", f);
    try { await api(`/workspaces/${ws.id}/upload?path=${encodeURIComponent(path)}`, { method: "POST", body: fd }); browse(ws.id, path); }
    finally { setUploading(false); }
  }

  async function del(e: any) {
    if (!confirm(`حذف ${e.name}؟`)) return;
    await api(`/workspaces/${ws.id}/file?path=${encodeURIComponent(e.path)}`, { method: "DELETE" });
    browse(ws.id, path);
  }

  return (
    <div className="space-y-5">
      <SectionTitle title="مدیریت فایل" sub="مرور، ویرایش، آپلود و دانلود فایل‌های فضای‌کار" />
      <div className="flex flex-wrap items-center gap-2">
        <select className="input max-w-xs" value={ws?.id || ""} onChange={(e) => { const w = wss.find((x) => x.id === e.target.value); setWs(w); browse(w.id, "."); }}>
          {wss.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <span className="mono rounded-lg bg-white/5 px-3 py-2 text-xs text-gray-400" dir="ltr">/{path.replace(/^\.\/?/, "")}</span>
        <input className="input max-w-[180px]" placeholder="نام پوشه جدید…" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button onClick={mkdir} className="btn-ghost text-xs">+ پوشه</button>
        <label className="btn-ghost cursor-pointer text-xs">
          {uploading ? "در حال آپلود…" : "آپلود فایل"}
          <input type="file" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="!p-0">
          <div className="border-b border-white/5 px-4 py-3 text-xs text-gray-400">{entries.length} مورد</div>
          {busy ? <div className="p-6 text-center"><Spinner /></div> : entries.length === 0 ? <Empty text="پوشه خالی است" /> : (
            <div className="divide-y divide-white/5">
              {path !== "." && (
                <button onClick={() => browse(ws.id, path.split("/").slice(0, -1).join("/") || ".")} className="flex w-full items-center gap-2 px-4 py-2.5 text-right text-sm text-gray-400 hover:bg-white/5">
                  ↰ پوشه بالاتر
                </button>
              )}
              {entries.map((e) => (
                <div key={e.path} className="flex items-center justify-between px-4 py-2.5 hover:bg-white/[.02]">
                  <button onClick={() => openFile(e)} className="flex min-w-0 items-center gap-2 text-right">
                    <span>{e.type === "dir" ? "📁" : "📄"}</span>
                    <span className="truncate text-sm text-gray-200">{e.name}</span>
                    <span className="shrink-0 text-[10px] text-gray-500">{e.type === "file" ? fmtBytes(e.size) : ""}</span>
                  </button>
                  <button onClick={() => del(e)} className="text-xs text-gray-600 hover:text-rose-400">حذف</button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          {file ? (
            <>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="mono truncate text-sm text-white" dir="ltr">{file.path}</h3>
                <a className="text-xs text-accent-400 hover:underline"
                  href={`/api/workspaces/${ws.id}/file?path=${encodeURIComponent(file.path)}&download=true&token=${localStorage.getItem("sina_token")}`}>دانلود</a>
              </div>
              <Code max="max-h-[60vh]">{file.content}</Code>
            </>
          ) : <Empty text="برای مشاهده محتوا روی یک فایل کلیک کنید" />}
        </Card>
      </div>
    </div>
  );
}
