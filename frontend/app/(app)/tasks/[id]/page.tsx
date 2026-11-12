"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, fa, fmtDate, sseUrl, TOOL_FA } from "@/lib/api";
import { Card, Code, Empty, SectionTitle, Spinner, StatusBadge, mdLite } from "@/components/ui";

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const [t, setT] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const esRef = useRef<EventSource | null>(null);

  const load = async () => {
    try {
      const d = await api(`/tasks/${id}`);
      setT(d);
      setLogs(await api(`/tasks/${id}/logs`).catch(() => []));
    } catch (e: any) { setErr(e.message); }
  };

  useEffect(() => {
    load();
    const es = new EventSource(sseUrl(id));
    esRef.current = es;
    const refresh = () => load();
    ["task.step", "tool.end", "task.status", "task.done", "approval.request"].forEach((ev) => es.addEventListener(ev, refresh));
    const iv = setInterval(() => { if (["running", "queued", "waiting_approval"].includes(t?.status)) load(); }, 4000);
    return () => { es.close(); clearInterval(iv); };
  }, [id]);

  async function cancel() { await api(`/tasks/${id}/cancel`, { method: "POST" }); load(); }
  async function decide(approve: boolean) {
    const ap = t?.approvals?.find((a: any) => a.status === "pending");
    if (!ap) return;
    await api(`/tasks/${id}/approvals/${ap.id}`, { method: "POST", body: JSON.stringify({ approve }) });
    load();
  }

  if (err) return <Card className="border-rose-500/30 text-rose-300">{err}</Card>;
  if (!t) return <div className="flex items-center gap-3 text-gray-400"><Spinner /> در حال بارگذاری…</div>;

  const active = ["running", "queued", "waiting_approval"].includes(t.status);
  const pendingAp = (t.approvals || []).find((a: any) => a.status === "pending");

  return (
    <div className="space-y-5">
      <SectionTitle title={t.title || "کار"} sub={`شناسه: ${t.id}`}
        action={<div className="flex items-center gap-2">
          <StatusBadge status={t.status} />
          {active && <button onClick={cancel} className="btn-danger !py-1.5 text-xs">لغو</button>}
          <Link href="/tasks" className="btn-ghost !py-1.5 text-xs">بازگشت</Link>
        </div>} />

      {pendingAp && (
        <Card className="border-orange-500/30 bg-orange-500/5">
          <p className="text-sm font-bold text-orange-200">⚠️ در انتظار تأیید شما: {pendingAp.description}</p>
          <pre dir="ltr" className="mono mt-2 max-h-40 overflow-auto rounded-lg bg-black/30 p-2 text-[11px] text-orange-100/70">{JSON.stringify(pendingAp.payload, null, 2)}</pre>
          <div className="mt-3 flex gap-2">
            <button onClick={() => decide(true)} className="btn bg-emerald-600 text-white hover:bg-emerald-500">تأیید</button>
            <button onClick={() => decide(false)} className="btn-ghost">رد</button>
          </div>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h3 className="mb-3 text-sm font-bold text-white">دستور</h3>
          <p className="text-sm leading-7 text-gray-300">{t.instruction}</p>
          <div className="mt-4 flex flex-wrap gap-4 text-[11px] text-gray-500">
            <span>نوع: {t.kind}</span><span>ریسک: {t.risk}</span><span>کانال: {t.channel}</span>
            <span>توکن ورودی: {fa(t.tokens_in)}</span><span>توکن خروجی: {fa(t.tokens_out)}</span>
            <span>هزینه: ${fa(t.cost_usd, 4)}</span><span>شروع: {fmtDate(t.created_at)}</span>
          </div>
          {t.result && (
            <div className="mt-5 rounded-xl border border-white/5 bg-white/[.02] p-4">
              <h4 className="mb-2 text-xs font-bold text-gray-300">گزارش نهایی</h4>
              <div className="prose-fa text-sm text-gray-200" dangerouslySetInnerHTML={mdLite(t.result)} />
            </div>
          )}
          {t.error && <div className="mt-4 rounded-xl bg-rose-500/10 p-3 text-xs text-rose-300">{t.error}</div>}
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">برنامه و گام‌ها</h3>
          {(t.steps || []).length === 0 ? <Empty text="گامی ثبت نشده" /> : (
            <ol className="space-y-3">
              {t.steps.map((s: any, i: number) => (
                <li key={i} className="flex gap-3">
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${s.status === "ok" ? "bg-emerald-400" : s.status === "error" ? "bg-rose-400" : "bg-amber-400"}`} />
                  <div>
                    <p className="text-xs font-medium text-gray-200">{s.phase}</p>
                    <p className="text-[11px] text-gray-500">{s.summary}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="mb-3 text-sm font-bold text-white">ابزارها و خروجی اجرا ({logs.length})</h3>
        {logs.length === 0 ? <Empty text="ابزاری اجرا نشده" /> : (
          <div className="space-y-3">
            {logs.map((l, i) => (
              <details key={i} className="rounded-xl border border-white/5 bg-ink-900/60" open={i === logs.length - 1}>
                <summary className="flex cursor-pointer items-center justify-between px-3 py-2 text-xs">
                  <span className="flex items-center gap-2">
                    <span className={l.exit_code === 0 || l.status === "ok" ? "text-emerald-400" : "text-rose-400"}>
                      {l.status === "ok" ? "✓" : "✕"}
                    </span>
                    <span className="font-medium text-gray-200">{TOOL_FA[l.tool] || l.tool}</span>
                    <span className="text-gray-500">{l.duration_ms}ms</span>
                  </span>
                  <span className="mono text-[10px] text-gray-600" dir="ltr">exit={l.exit_code ?? "—"}</span>
                </summary>
                <div className="border-t border-white/5 p-3">
                  <Code max="max-h-64">{JSON.stringify(l.args, null, 2)}</Code>
                  {l.output && <Code max="max-h-80" className="mt-2">{l.output}</Code>}
                </div>
              </details>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
