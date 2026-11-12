"use client";
import { useEffect, useState } from "react";
import { api, fa } from "@/lib/api";
import { Card, Empty, SectionTitle, Stat } from "@/components/ui";

export default function UsagePage() {
  const [d, setD] = useState<any>(null);
  useEffect(() => { api("/usage/summary?days=30").then(setD).catch(() => {}); }, []);

  const max = Math.max(1, ...(d?.by_day || []).map((x: any) => x.cost));

  return (
    <div className="space-y-5">
      <SectionTitle title="مصرف و هزینه" sub="توکن مصرفی و هزینه تخمینی مدل‌ها در ۳۰ روز گذشته" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="هزینه کل" value={`$${fa(d?.totals?.cost_usd || 0, 4)}`} accent="text-accent-400" />
        <Stat label="تعداد فراخوانی" value={fa(d?.totals?.calls || 0)} />
        <Stat label="توکن ورودی" value={fa(d?.totals?.tokens_in || 0)} />
        <Stat label="توکن خروجی" value={fa(d?.totals?.tokens_out || 0)} />
      </div>

      <Card>
        <h3 className="mb-4 text-sm font-bold text-white">هزینه روزانه</h3>
        {(d?.by_day || []).length === 0 ? <Empty text="داده‌ای موجود نیست" /> : (
          <div className="flex h-40 items-end gap-1">
            {(d.by_day || []).map((x: any) => (
              <div key={x.date} className="group relative flex-1" title={`${x.date}: $${x.cost.toFixed(4)}`}>
                <div className="w-full rounded-t bg-gradient-to-t from-brand-600 to-accent-500 transition group-hover:brightness-125"
                  style={{ height: `${Math.max(4, (x.cost / max) * 150)}px` }} />
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="!p-0">
        <div className="border-b border-white/5 px-4 py-3 text-sm font-bold text-white">به تفکیک مدل</div>
        {(d?.by_model || []).length === 0 ? <Empty text="داده‌ای موجود نیست" /> : (
          <table className="w-full text-xs">
            <thead className="text-gray-500"><tr>
              <th className="p-3 text-right font-medium">مدل</th><th className="p-3 text-right font-medium">فراخوانی</th>
              <th className="p-3 text-right font-medium">ورودی</th><th className="p-3 text-right font-medium">خروجی</th>
              <th className="p-3 text-right font-medium">هزینه</th></tr></thead>
            <tbody className="divide-y divide-white/5">
              {d.by_model.map((m: any) => (
                <tr key={m.model}>
                  <td className="mono p-3 text-gray-200" dir="ltr">{m.model}</td>
                  <td className="p-3 text-gray-400">{fa(m.calls)}</td>
                  <td className="p-3 text-gray-400">{fa(m.tokens_in)}</td>
                  <td className="p-3 text-gray-400">{fa(m.tokens_out)}</td>
                  <td className="p-3 text-accent-400">${fa(m.cost, 4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
