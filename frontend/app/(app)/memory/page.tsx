"use client";
import { useEffect, useState } from "react";
import { api, fmtDate } from "@/lib/api";
import { Card, Empty, SectionTitle, Spinner } from "@/components/ui";

const KINDS: Record<string, string> = { fact: "واقعیت", preference: "ترجیح", project: "پروژه", episodic: "رویداد", note: "یادداشت" };

export default function MemoryPage() {
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("fact");
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);

  const load = () => api<any[]>("/memory").then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  async function search() {
    if (!q.trim()) { setSearched(false); return load(); }
    setBusy(true);
    try { setItems(await api<any[]>(`/memory?q=${encodeURIComponent(q)}`)); setSearched(true); }
    finally { setBusy(false); }
  }
  async function add() {
    if (!content.trim()) return;
    await api("/memory", { method: "POST", body: JSON.stringify({ content, kind }) });
    setContent(""); load();
  }
  async function del(id: string) { await api(`/memory/${id}`, { method: "DELETE" }); load(); }

  return (
    <div className="space-y-5">
      <SectionTitle title="حافظه" sub="خاطرات بلندمدت عامل: ترجیحات، حقایق و اطلاعات پروژه‌ها" />
      <Card>
        <div className="flex flex-wrap gap-2">
          <input className="input flex-1" placeholder="جست‌وجوی معنایی در حافظه…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
          <button onClick={search} disabled={busy} className="btn-ghost shrink-0 text-xs">{busy ? <Spinner /> : "جست‌وجو"}</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <select className="input max-w-[140px]" value={kind} onChange={(e) => setKind(e.target.value)}>
            {Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="input flex-1" placeholder="افزودن یادداشت جدید…" value={content} onChange={(e) => setContent(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} />
          <button onClick={add} className="btn-primary shrink-0 text-xs">ذخیره</button>
        </div>
      </Card>

      {items.length === 0 ? <Card><Empty text="حافظه‌ای ثبت نشده است" /></Card> : (
        <div className="space-y-3">
          {items.map((m) => (
            <Card key={m.id} className="card-hover">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="mb-1 flex items-center gap-2">
                    <span className="chip bg-brand-500/10 text-brand-300">{KINDS[m.kind] || m.kind}</span>
                    {m.score != null && <span className="chip bg-accent-500/10 text-accent-400">تطابق {m.score}</span>}
                    {m.has_embedding && <span className="chip bg-emerald-500/10 text-emerald-300">برداری</span>}
                  </div>
                  <p className="text-sm leading-7 text-gray-200">{m.content}</p>
                  <p className="mt-1 text-[10px] text-gray-500">{fmtDate(m.created_at)}</p>
                </div>
                <button onClick={() => del(m.id)} className="text-xs text-gray-600 hover:text-rose-400">حذف</button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
