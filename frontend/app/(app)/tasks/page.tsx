"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fa, fmtDate } from "@/lib/api";
import { Card, Empty, SectionTitle, StatusBadge } from "@/components/ui";

const FILTERS = [
  { v: "", l: "همه" }, { v: "running", l: "در حال اجرا" }, { v: "queued", l: "در صف" },
  { v: "waiting_approval", l: "در انتظار تأیید" }, { v: "completed", l: "تکمیل‌شده" },
  { v: "failed", l: "ناموفق" }, { v: "cancelled", l: "لغوشده" },
];

export default function TasksPage() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [f, setF] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => {
    const load = () => api<any[]>(`/tasks?limit=100${f ? `&status=${f}` : ""}`).then(setTasks).catch(() => {});
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, [f]);

  const shown = tasks.filter((t) => !q || (t.title || "").includes(q));

  return (
    <div className="space-y-5">
      <SectionTitle title="کارها" sub="همه وظایف اجراشده توسط عامل هوشمند، با وضعیت زنده" />
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((x) => (
          <button key={x.v} onClick={() => setF(x.v)}
            className={`chip border ${f === x.v ? "border-brand-500/50 bg-brand-600/20 text-white" : "border-white/10 bg-white/5 text-gray-400 hover:text-gray-200"}`}>
            {x.l}
          </button>
        ))}
        <input className="input mr-auto max-w-xs" placeholder="جست‌وجو…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      <Card className="!p-0">
        {shown.length === 0 ? <Empty text="کاری یافت نشد" /> : (
          <table className="w-full text-sm">
            <thead className="border-b border-white/5 text-[11px] text-gray-500">
              <tr>
                <th className="p-3 text-right font-medium">عنوان</th>
                <th className="p-3 text-right font-medium">وضعیت</th>
                <th className="hidden p-3 text-right font-medium md:table-cell">نوع</th>
                <th className="hidden p-3 text-right font-medium md:table-cell">کانال</th>
                <th className="hidden p-3 text-right font-medium lg:table-cell">هزینه</th>
                <th className="p-3 text-right font-medium">زمان</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {shown.map((t) => (
                <tr key={t.id} className="transition hover:bg-white/[.02]">
                  <td className="max-w-[380px] p-3">
                    <Link href={`/tasks/${t.id}`} className="block truncate text-gray-200 hover:text-white">{t.title}</Link>
                  </td>
                  <td className="p-3"><StatusBadge status={t.status} /></td>
                  <td className="hidden p-3 text-xs text-gray-400 md:table-cell">{t.kind}</td>
                  <td className="hidden p-3 text-xs text-gray-400 md:table-cell">{t.channel}</td>
                  <td className="hidden p-3 text-xs text-gray-400 lg:table-cell">${fa(t.cost_usd || 0, 4)}</td>
                  <td className="p-3 text-xs text-gray-500">{fmtDate(t.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
