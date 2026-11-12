"use client";
import { useEffect, useState } from "react";
import { api, fa } from "@/lib/api";
import { Card, Empty, Meter, SectionTitle, Stat } from "@/components/ui";

export default function SystemPage() {
  const [s, setS] = useState<any>(null);
  const [tools, setTools] = useState<any[]>([]);

  useEffect(() => {
    const load = () => api("/system/stats").then(setS).catch(() => {});
    load();
    api("/system/tools").then(setTools).catch(() => {});
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="space-y-5">
      <SectionTitle title="پایش سیستم" sub="وضعیت لحظه‌ای میزبان، سرویس‌ها و پورت‌ها" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="میزبان" value={s?.host?.hostname || "—"} hint={s?.host?.os} />
        <Stat label="آپ‌تایم" value={`${fa(s?.host?.uptime_hours || 0)} ساعت`} />
        <Stat label="جداسازی اجرا" value={s?.docker?.isolation === "container" ? "کانتینر ایزوله" : (s?.docker?.available ? "Docker" : "—")}
          hint={s?.docker?.note} accent={s?.docker?.isolation === "container" ? "text-emerald-400" : "text-amber-400"} />
        <Stat label="پورت‌های فعال" value={fa((s?.ports || []).length)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-5">
          <h3 className="text-sm font-bold text-white">منابع</h3>
          <Meter label="پردازنده" percent={s?.cpu?.percent || 0} detail={`بار سیستم: ${(s?.cpu?.load || []).map((x: number) => x.toFixed(2)).join(" / ") || "—"}`} />
          <Meter label="حافظه" percent={s?.memory?.percent || 0} detail={`${s?.memory?.used_gb} از ${s?.memory?.total_gb} گیگابایت`} />
          <Meter label="دیسک" percent={s?.disk?.percent || 0} detail={`${s?.disk?.used_gb} از ${s?.disk?.total_gb} گیگابایت`} />
        </Card>
        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">پورت‌های در حال گوش‌دادن</h3>
          <div className="flex flex-wrap gap-2">
            {(s?.ports || []).map((p: number) => <span key={p} className="mono chip bg-white/5 text-gray-300" dir="ltr">{p}</span>)}
            {(s?.ports || []).length === 0 && <p className="text-xs text-gray-500">داده‌ای در دسترس نیست</p>}
          </div>
          <h3 className="mb-3 mt-6 text-sm font-bold text-white">پرمصرف‌ترین فرآیندها</h3>
          <div className="space-y-1.5">
            {(s?.top_processes || []).map((p: any) => (
              <div key={p.pid} className="flex items-center justify-between text-xs">
                <span className="mono truncate text-gray-300" dir="ltr">{p.name}</span>
                <span className="text-gray-500">CPU {p.cpu}% · MEM {p.mem}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="!p-0">
        <div className="border-b border-white/5 px-4 py-3 text-sm font-bold text-white">ابزارهای ثبت‌شده عامل ({tools.length})</div>
        <div className="grid gap-2 p-4 md:grid-cols-2">
          {tools.map((t) => (
            <div key={t.name} className="rounded-xl border border-white/5 bg-white/[.02] p-3">
              <div className="flex items-center justify-between">
                <span className="mono text-xs text-gray-200" dir="ltr">{t.name}</span>
                <span className={`chip ${t.risk === "safe" ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"}`}>{t.risk}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-gray-400">{t.description}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
