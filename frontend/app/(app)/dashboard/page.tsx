"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fa, fmtDate, getUser } from "@/lib/api";
import { Card, Empty, Meter, SectionTitle, Stat, StatusBadge } from "@/components/ui";

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [quick, setQuick] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    const load = () => {
      api("/system/stats").then(setStats).catch((e) => setErr(e.message));
      api("/tasks?limit=6").then(setTasks).catch(() => {});
    };
    load();
    const iv = setInterval(load, 8000);
    return () => clearInterval(iv);
  }, []);

  async function send() {
    if (!quick.trim()) return;
    setSending(true);
    try {
      const r = await api("/tasks", { method: "POST", body: JSON.stringify({ instruction: quick }) });
      location.href = `/tasks/${r.task.id}`;
    } finally { setSending(false); }
  }

  const u = getUser();
  return (
    <div className="space-y-6">
      <SectionTitle title={`سلام ${u?.name || ""} 👋`}
        sub="وضعیت لحظه‌ای سیستم‌عامل شخصی شما و آخرین کارها"
        action={<Link href="/chat" className="btn-ghost text-xs">گفتگوی کامل</Link>} />

      {err && <Card className="border-rose-500/30 text-sm text-rose-300">{err}</Card>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="کارهای در حال اجرا" value={fa(stats?.counts?.running_tasks || 0)} hint="AGENT WORKER" accent="text-brand-300" />
        <Stat label="کل کارها" value={fa(stats?.counts?.tasks || 0)} hint="TASKS" />
        <Stat label="گفتگوها" value={fa(stats?.counts?.conversations || 0)} hint="CONVERSATIONS" />
        <Stat label="خاطرات ذخیره‌شده" value={fa(stats?.counts?.memories || 0)} hint="MEMORY" accent="text-accent-400" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-sm font-bold text-white">یک دستور جدید به سینا بدهید</h3>
          <div className="flex gap-2">
            <input className="input" placeholder="مثال: یک اپلیکیشن پایتون بساز، تست کن و خروجی را بده…"
              value={quick} onChange={(e) => setQuick(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()} />
            <button onClick={send} disabled={sending} className="btn-primary shrink-0">{sending ? "…" : "اجرا"}</button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {["یک وب‌سایت فروشگاهی کامل بساز", "تحقیق اینترنتی درباره LangGraph انجام بده", "سلامت سرور را بررسی کن"].map((s) => (
              <button key={s} onClick={() => setQuick(s)} className="chip border border-white/10 bg-white/5 text-gray-300 hover:bg-white/10">{s}</button>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-bold text-white">سلامت میزبان</h3>
          <div className="space-y-4">
            <Meter label="پردازنده" percent={stats?.cpu?.percent || 0} detail={`${stats?.cpu?.cores || "-"} هسته`} />
            <Meter label="حافظه" percent={stats?.memory?.percent || 0}
              detail={`${stats?.memory?.used_gb ?? "-"} از ${stats?.memory?.total_gb ?? "-"} گیگابایت`} />
            <Meter label="دیسک" percent={stats?.disk?.percent || 0}
              detail={`${stats?.disk?.used_gb ?? "-"} از ${stats?.disk?.total_gb ?? "-"} گیگابایت`} />
          </div>
          <div className="mt-4 flex items-center justify-between text-[11px] text-gray-500">
            <span>Docker: {stats?.docker?.available ? "در دسترس" : "غیرفعال"}</span>
            <Link href="/system" className="text-accent-400 hover:underline">جزئیات ←</Link>
          </div>
        </Card>
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white">آخرین کارها</h3>
          <Link href="/tasks" className="text-xs text-accent-400 hover:underline">همه کارها ←</Link>
        </div>
        {tasks.length === 0 ? <Empty text="هنوز کاری اجرا نشده است" /> : (
          <div className="divide-y divide-white/5">
            {tasks.map((t) => (
              <Link key={t.id} href={`/tasks/${t.id}`} className="flex items-center justify-between gap-3 py-3 transition hover:bg-white/[.02]">
                <div className="min-w-0">
                  <p className="truncate text-sm text-gray-200">{t.title}</p>
                  <p className="mt-0.5 text-[11px] text-gray-500">{fmtDate(t.created_at)} · {t.kind}</p>
                </div>
                <StatusBadge status={t.status} />
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
