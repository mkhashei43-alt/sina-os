"use client";
import { useEffect, useState } from "react";
import { api, fa } from "@/lib/api";
import { Card, SectionTitle, Spinner } from "@/components/ui";

export default function ModelsPage() {
  const [d, setD] = useState<any>(null);
  const [form, setForm] = useState({ default_model: "", coding_model: "", reasoning_model: "" });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api("/models").then((r) => { setD(r); setForm({ default_model: r.default_model, coding_model: r.coding_model, reasoning_model: r.reasoning_model }); }).catch(() => {});
  }, []);

  async function save() {
    await api("/models", { method: "POST", body: JSON.stringify(form) });
    setSaved(true); setTimeout(() => setSaved(false), 2500);
  }

  if (!d) return <div className="flex gap-2 text-gray-400"><Spinner /> بارگذاری…</div>;

  return (
    <div className="space-y-5">
      <SectionTitle title="مدل‌ها" sub="انتخاب مدل‌های OpenRouter برای هر نقش؛ بدون تغییر کد" />
      <Card>
        <div className="mb-4 flex items-center gap-2 text-xs">
          <span className={`chip ${d.configured ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300"}`}>
            ارائه‌دهنده: {d.provider}
          </span>
          <span className="text-gray-500">{d.configured ? "کلید API تنظیم شده است" : "کلید OPENROUTER_API_KEY تنظیم نشده — حالت آزمون فعال است"}</span>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {[["default_model", "مدل پیش‌فرض", "گفتگو و کارهای عمومی"], ["coding_model", "مدل کدنویسی", "پروژه‌های نرم‌افزاری"], ["reasoning_model", "مدل استدلال", "برنامه‌ریزی و تحلیل"]].map(([k, l, h]) => (
            <div key={k}>
              <label className="label">{l}</label>
              <input className="input mono" dir="ltr" value={(form as any)[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              <p className="mt-1 text-[11px] text-gray-500">{h}</p>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button onClick={save} className="btn-primary text-xs">ذخیره تنظیمات</button>
          {saved && <span className="text-xs text-emerald-400">ذخیره شد ✓</span>}
        </div>
      </Card>

      <Card className="!p-0">
        <div className="border-b border-white/5 px-4 py-3 text-sm font-bold text-white">کاتالوگ مدل‌های موجود ({fa(d.catalog?.length || 0)})</div>
        <div className="max-h-[50vh] overflow-y-auto">
          {(d.catalog || []).map((m: any) => (
            <div key={m.id} className="flex items-center justify-between border-b border-white/5 px-4 py-2.5 text-xs last:border-0">
              <div className="min-w-0">
                <p className="truncate text-gray-200">{m.name}</p>
                <p className="mono truncate text-[10px] text-gray-500" dir="ltr">{m.id}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {m.context && <span className="chip bg-white/5 text-gray-400">{(m.context / 1000).toFixed(0)}K</span>}
                <button onClick={() => setForm({ ...form, default_model: m.id })} className="chip bg-brand-500/10 text-brand-300 hover:bg-brand-500/20">انتخاب</button>
              </div>
            </div>
          ))}
          {(!d.catalog || d.catalog.length === 0) && <p className="p-4 text-xs text-gray-500">برای مشاهده کاتالوگ، کلید OpenRouter را تنظیم کنید.</p>}
        </div>
      </Card>
    </div>
  );
}
