"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fmtDate } from "@/lib/api";
import { Card, Empty, SectionTitle } from "@/components/ui";

export default function WorkspacesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [name, setName] = useState("");

  const load = () => api<any[]>("/workspaces").then(setItems).catch(() => {});
  useEffect(() => { load(); }, []);

  async function create() {
    if (!name.trim()) return;
    await api("/workspaces", { method: "POST", body: JSON.stringify({ name }) });
    setName(""); load();
  }
  async function remove(id: string) {
    if (!confirm("این فضای‌کار و همه فایل‌هایش حذف شود؟")) return;
    await api(`/workspaces/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <div className="space-y-5">
      <SectionTitle title="فضای‌کار" sub="محیط‌های ایزوله اجرا با فایل، ترمینال و اجرای کد" />
      <Card>
        <div className="flex gap-2">
          <input className="input" placeholder="نام فضای‌کار جدید…" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
          <button onClick={create} className="btn-primary shrink-0">ساخت</button>
        </div>
      </Card>
      {items.length === 0 ? <Card><Empty text="فضای‌کاری وجود ندارد" /></Card> : (
        <div className="grid gap-4 md:grid-cols-2">
          {items.map((w) => (
            <Card key={w.id} className="card-hover">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate font-bold text-white">{w.name}</h3>
                  <p className="mono mt-1 truncate text-[10px] text-gray-500" dir="ltr">{w.path}</p>
                </div>
                <span className="chip shrink-0 bg-brand-500/10 text-brand-300">{w.files} فایل</span>
              </div>
              <p className="mt-2 text-[11px] text-gray-500">ساخته‌شده: {fmtDate(w.created_at)}</p>
              <div className="mt-3 flex gap-2">
                <Link href={`/files?ws=${w.id}`} className="btn-ghost flex-1 !py-1.5 text-xs">فایل‌ها</Link>
                <Link href={`/terminal?ws=${w.id}`} className="btn-ghost flex-1 !py-1.5 text-xs">ترمینال</Link>
                <button onClick={() => remove(w.id)} className="btn-danger !py-1.5 text-xs">حذف</button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
