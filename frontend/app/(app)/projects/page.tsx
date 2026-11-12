"use client";
import { useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";
import { Card, Empty, Modal, SectionTitle, Spinner } from "@/components/ui";

export default function ProjectsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", stack: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const load = () => api<any[]>("/projects").then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create() {
    setBusy(true); setMsg("");
    try {
      await api("/projects", { method: "POST", body: JSON.stringify({ ...form, stack: form.stack.split(",").map((s) => s.trim()).filter(Boolean) }) });
      setOpen(false); setForm({ name: "", description: "", stack: "" }); load();
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-5">
      <SectionTitle title="پروژه‌ها" sub="پروژه‌های ساخته‌شده با فضای‌کار اختصاصی و حافظه مخصوص"
        action={<button onClick={() => setOpen(true)} className="btn-primary text-xs">+ پروژه جدید</button>} />
      {items.length === 0 ? <Card><Empty text="هنوز پروژه‌ای ساخته نشده است" /></Card> : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {items.map((p) => (
            <Card key={p.id} className="card-hover">
              <div className="flex items-start justify-between">
                <h3 className="font-bold text-white">{p.name}</h3>
                <span className="chip bg-emerald-500/10 text-emerald-300">{p.status}</span>
              </div>
              <p className="mt-2 line-clamp-2 min-h-[2.5rem] text-xs text-gray-400">{p.description || "بدون توضیح"}</p>
              <div className="mt-3 flex flex-wrap gap-1">
                {(p.stack || []).map((s: string) => <span key={s} className="chip bg-brand-500/10 text-brand-300">{s}</span>)}
              </div>
              <div className="mt-3 flex items-center justify-between text-[11px] text-gray-500">
                <span>{p.tasks} کار</span><span>{fmtDate(p.created_at)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="پروژه جدید">
        <div className="space-y-3">
          <div><label className="label">نام پروژه</label><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div><label className="label">توضیحات</label><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          <div><label className="label">تکنولوژی‌ها (با کاما)</label><input className="input" dir="ltr" placeholder="python, fastapi" value={form.stack} onChange={(e) => setForm({ ...form, stack: e.target.value })} /></div>
          {msg && <p className="text-xs text-rose-300">{msg}</p>}
          <button onClick={create} disabled={busy || !form.name} className="btn-primary w-full">{busy ? <Spinner /> : "ساخت پروژه"}</button>
        </div>
      </Modal>
    </div>
  );
}
