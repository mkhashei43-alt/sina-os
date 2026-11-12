"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Card, Empty, SectionTitle, Spinner } from "@/components/ui";

export default function BrowserPage() {
  const [url, setUrl] = useState("");
  const [page, setPage] = useState<any>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function go(target?: string) {
    const u = target || url;
    if (!u) return;
    setBusy(true); setErr(""); setResults([]);
    try {
      const r = await api(`/web/fetch?url=${encodeURIComponent(u)}`);
      setPage(r); setUrl(r.url);
    } catch (e: any) { setErr(e.message); setPage(null); } finally { setBusy(false); }
  }

  async function search() {
    if (!q.trim()) return;
    setBusy(true); setErr(""); setPage(null);
    try { const r = await api(`/web/search?q=${encodeURIComponent(q)}`); setResults(r.results || []); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <SectionTitle title="مرورگر" sub="مرور و استخراج محتوای صفحات وب به‌صورت امن (بدون اجرای اسکریپت)" />
      <Card>
        <div className="flex flex-wrap gap-2">
          <input className="input flex-1" dir="ltr" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} onKeyDown={(e) => e.key === "Enter" && go()} />
          <button onClick={() => go()} disabled={busy} className="btn-primary shrink-0 text-xs">بازکردن</button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <input className="input flex-1" placeholder="جست‌وجوی وب…" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
          <button onClick={search} disabled={busy} className="btn-ghost shrink-0 text-xs">جست‌وجو</button>
        </div>
      </Card>

      {err && <Card className="border-rose-500/30 text-sm text-rose-300">{err}</Card>}
      {busy && <div className="flex items-center gap-2 text-sm text-gray-400"><Spinner /> در حال دریافت…</div>}

      {results.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">نتایج جست‌وجو</h3>
          <div className="space-y-3">
            {results.map((r, i) => (
              <div key={i} className="rounded-xl border border-white/5 p-3">
                <button onClick={() => go(r.url)} className="text-sm font-medium text-accent-400 hover:underline">{r.title}</button>
                <p className="mono mt-0.5 truncate text-[10px] text-gray-500" dir="ltr">{r.url}</p>
                <p className="mt-1 text-xs text-gray-400">{r.snippet}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {page && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">محتوای استخراج‌شده</h3>
            <span className="chip bg-emerald-500/10 text-emerald-300">HTTP {page.status}</span>
          </div>
          <pre className="max-h-[55vh] overflow-auto whitespace-pre-wrap text-xs leading-7 text-gray-300">{page.text}</pre>
        </Card>
      )}
      {!page && !busy && results.length === 0 && <Card><Empty text="یک آدرس وارد کنید یا جست‌وجو کنید" /></Card>}
    </div>
  );
}
