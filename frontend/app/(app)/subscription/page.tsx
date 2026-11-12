"use client";
import { useEffect, useState } from "react";
import { api, fa, fmtDate } from "@/lib/api";
import { Card, SectionTitle, Meter } from "@/components/ui";

const STATUS_FA: Record<string, string> = { pending: "در انتظار پرداخت", approved: "تأییدشده", rejected: "ردشده" };
const STATUS_CLS: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-300",
  rejected: "bg-rose-500/15 text-rose-300",
};

export default function SubscriptionPage() {
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ plan: "pro", months: 1, reference: "", note: "" });

  const load = () => api("/billing/me").then((d) => {
    setData(d);
    const cur = d?.plan?.key;
    setForm((f) => ({ ...f, plan: cur === "pro" ? "business" : cur === "business" ? "business" : "pro" }));
  }).catch(() => {});
  useEffect(() => { load(); }, []);

  async function submit() {
    setBusy(true); setMsg("");
    try {
      const r = await api("/billing/request", { method: "POST", body: JSON.stringify(form) });
      setMsg(`درخواست ثبت شد — مبلغ ${fa(r.amount_toman)} تومان. پس از واریز و تأیید مدیر فعال می‌شود.`);
      load();
    } catch (e: any) { setMsg(e.message || "خطا در ثبت درخواست"); }
    finally { setBusy(false); }
  }

  async function cancel(id: string) {
    await api(`/billing/cancel-request/${id}`, { method: "POST" }).catch(() => {});
    load();
  }

  if (!data) return <p className="p-6 text-sm text-gray-400">در حال بارگذاری…</p>;
  const plan = data.plan, usage = data.usage, tenant = data.tenant;
  const titles: Record<string, string> = { free: "رایگان", pro: "حرفه‌ای", business: "کسب‌وکار" };

  return (
    <div className="space-y-5">
      <SectionTitle title="اشتراک و سهمیه" sub="پلن فعلی، مصرف این ماه، و درخواست ارتقا" />

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className={plan.key !== "free" ? "border-brand-500/30" : ""}>
          <p className="text-[11px] text-gray-500">پلن فعلی</p>
          <div className="mt-1 flex items-baseline gap-2">
            <h2 className="text-2xl font-black text-white">{titles[plan.key] || plan.name}</h2>
            {tenant?.status === "trial" && (
              <span className="chip bg-amber-500/15 text-amber-300">
                آزمایشی — {fa(tenant.trial_days_left || 0)} روز باقی‌مانده
              </span>
            )}
            {tenant?.status === "active" && <span className="chip bg-emerald-500/15 text-emerald-300">فعال</span>}
          </div>
          <p className="mt-3 text-[12px] text-gray-400">
            {plan.price_toman ? `${fa(plan.price_toman)} تومان در ماه` : "بدون هزینه"}
          </p>
          <div className="mt-4 space-y-3">
            <Meter label="کارهای امروز" percent={usage.tasks_pct} detail={`${fa(usage.tasks_today)} از ${fa(plan.tasks_per_day)}`} />
            <Meter label="توکن‌های این ماه" percent={usage.tokens_pct} detail={`${fa(usage.tokens_month)} از ${fa(plan.tokens_per_month)}`} />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-center">
            <div className="rounded-xl bg-white/5 py-2">
              <p className="text-sm font-bold text-white">{fa(usage.workspaces)} / {fa(plan.workspaces)}</p>
              <p className="text-[10.5px] text-gray-500">فضای‌کار</p>
            </div>
            <div className="rounded-xl bg-white/5 py-2">
              <p className="text-sm font-bold text-white">{fa(usage.credentials)} / {fa(plan.credentials)}</p>
              <p className="text-[10.5px] text-gray-500">اتصال خارجی</p>
            </div>
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <h3 className="text-sm font-bold text-white">درخواست ارتقا / تمدید</h3>
          <p className="mt-1 text-[11.5px] leading-6 text-gray-400">
            پس از ثبت درخواست، مبلغ را کارت‌به‌کارت کنید و شمارهٔ پیگیری را بفرستید؛
            پلن پس از تأیید مدیر فعال می‌شود.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div>
              <label className="label">پلن</label>
              <select className="input" value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value })}>
                {(data.catalog || []).filter((p: any) => p.price_toman > 0).map((p: any) => (
                  <option key={p.key} value={p.key}>{p.name} — {fa(p.price_toman)} تومان/ماه</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">دوره</label>
              <select className="input" value={form.months} onChange={(e) => setForm({ ...form, months: Number(e.target.value) })}>
                {[1, 3, 6, 12].map((m) => <option key={m} value={m}>{m} ماه{m === 12 ? " (۲ ماه هدیه)" : ""}</option>)}
              </select>
            </div>
            <div>
              <label className="label">شماره پیگیری واریز (اختیاری)</label>
              <input className="input" dir="ltr" value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="REF-12345" />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-[12px] text-gray-400">
              مبلغ قابل پرداخت: <b className="text-white">
                {fa(((data.catalog || []).find((p: any) => p.key === form.plan)?.price_toman || 0) * form.months)} تومان
              </b>
            </p>
            <button onClick={submit} disabled={busy} className="btn-primary text-xs">{busy ? "در حال ثبت…" : "ثبت درخواست ارتقا"}</button>
          </div>
          {msg && <p className="mt-3 rounded-lg bg-brand-500/10 px-3 py-2 text-[12px] leading-6 text-brand-200">{msg}</p>}
        </Card>
      </div>

      <Card>
        <h3 className="mb-4 text-sm font-bold text-white">تاریخچهٔ درخواست‌ها و فاکتورها</h3>
        {data.requests?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-[12.5px]">
              <thead className="text-[11px] text-gray-500">
                <tr><th className="pb-2">تاریخ</th><th className="pb-2">پلن</th><th className="pb-2">دوره</th><th className="pb-2">مبلغ</th><th className="pb-2">وضعیت</th><th className="pb-2" /></tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.requests.map((r: any) => (
                  <tr key={r.id}>
                    <td className="py-2.5 text-gray-400">{fmtDate(r.created_at)}</td>
                    <td className="py-2.5 text-gray-200">{titles[r.plan] || r.plan}</td>
                    <td className="py-2.5 text-gray-400">{fa(r.months)} ماه</td>
                    <td className="py-2.5 text-gray-200">{fa(r.amount_toman)} تومان</td>
                    <td className="py-2.5"><span className={`chip ${STATUS_CLS[r.status]}`}>{STATUS_FA[r.status] || r.status}</span></td>
                    <td className="py-2.5 text-left">
                      {r.status === "pending" && (
                        <button onClick={() => cancel(r.id)} className="text-[11px] text-rose-300 hover:underline">لغو</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-gray-500">هنوز درخواستی ثبت نکرده‌اید.</p>
        )}
      </Card>

      <Card className="border-white/5">
        <h3 className="text-sm font-bold text-white">پرداخت و پشتیبانی</h3>
        <p className="mt-2 text-[12px] leading-7 text-gray-400">
          برای هماهنگی واریز و ارسال رسید با پشتیبانی در ارتباط باشید. پس از تأیید، پلن بلافاصله فعال و در همین صفحه نمایش داده می‌شود.
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-[12px]">
          {data.payment?.telegram && (
            <a href={`https://t.me/${data.payment.telegram}`} target="_blank" className="btn-ghost !py-1.5 text-xs">تلگرام پشتیبانی</a>
          )}
          {data.payment?.card && <span className="chip bg-white/5 text-gray-300">ایمیل: {data.payment.card}</span>}
        </div>
      </Card>
    </div>
  );
}
