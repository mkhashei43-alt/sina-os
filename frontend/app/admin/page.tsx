"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, fa, fmtDate, getUser } from "@/lib/api";

const PLAN_FA: Record<string, string> = { free: "رایگان", pro: "حرفه‌ای", business: "کسب‌وکار" };
const STATUS_FA: Record<string, string> = { trial: "آزمایشی", active: "فعال", suspended: "تعلیق", closed: "بسته" };
const STATUS_CLS: Record<string, string> = {
  trial: "bg-amber-500/15 text-amber-300", active: "bg-emerald-500/15 text-emerald-300",
  suspended: "bg-rose-500/15 text-rose-300", closed: "bg-gray-500/15 text-gray-400",
  pending: "bg-amber-500/15 text-amber-300", approved: "bg-emerald-500/15 text-emerald-300",
  rejected: "bg-rose-500/15 text-rose-300",
};

export default function AdminPage() {
  const [tab, setTab] = useState<"tenants" | "requests" | "audit">("tenants");
  const [overview, setOverview] = useState<any>(null);
  const [tenants, setTenants] = useState<any[]>([]);
  const [requests, setRequests] = useState<any[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [denied, setDenied] = useState(false);

  async function load() {
    try {
      const [o, t, r] = await Promise.all([
        api("/admin/overview"), api(`/admin/tenants${q ? `?q=${encodeURIComponent(q)}` : ""}`),
        api("/admin/requests?status=all"),
      ]);
      setOverview(o); setTenants(t); setRequests(r);
    } catch (e: any) {
      if (e.status === 403) setDenied(true);
      else setErr(e.message || "خطا");
    }
  }
  useEffect(() => { load(); }, []);

  async function patch(id: string, body: any) {
    await api(`/admin/tenants/${id}`, { method: "PATCH", body: JSON.stringify(body) }).catch((e) => setErr(e.message));
    load();
  }
  async function decide(id: string, approve: boolean) {
    await api(`/admin/requests/${id}/decide`, { method: "POST", body: JSON.stringify({ approve }) }).catch((e) => setErr(e.message));
    load();
  }
  async function openAudit() {
    setTab("audit");
    setAudit(await api("/admin/audit?limit=120").catch(() => []));
  }

  if (denied) return (
    <div className="grid min-h-screen place-items-center p-6 text-center">
      <div className="card max-w-md p-8">
        <p className="text-3xl">🔒</p>
        <h1 className="mt-3 text-lg font-bold text-white">دسترسی ندارید</h1>
        <p className="mt-2 text-sm text-gray-400">
          این صفحه فقط برای مدیر پلتفرم است. اگر باید دسترسی داشته باشید، ایمیل خود را در
          <code className="mx-1 rounded bg-white/10 px-1.5 py-0.5 text-[11px]">PLATFORM_ADMIN_EMAILS</code>
          سرور اضافه کنید.
        </p>
        <Link href="/dashboard" className="btn-ghost mt-5 text-xs">بازگشت به داشبورد</Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen p-5 lg:p-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-black text-white">پنل مدیریت پلتفرم</h1>
            <p className="mt-1 text-[12px] text-gray-400">مشتری‌ها، درآمد، درخواست‌های ارتقا و رخدادها</p>
          </div>
          <div className="flex gap-2">
            <Link href="/dashboard" className="btn-ghost text-xs">داشبورد سینا</Link>
            <button onClick={load} className="btn-primary text-xs">به‌روزرسانی</button>
          </div>
        </header>

        {err && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{err}</p>}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { l: "کل مشتری‌ها", v: fa(overview?.tenants || 0), h: `${fa(overview?.trials || 0)} آزمایشی` },
            { l: "درآمد تأییدشدهٔ این ماه", v: `${fa(overview?.mrr_toman || 0)} ت`, h: "از درخواست‌های تأییدشده" },
            { l: "درخواست در انتظار", v: fa(overview?.pending_requests || 0), h: "نیازمند بررسی" },
            { l: "توکن مصرفی ماه", v: fa(overview?.tokens_month || 0), h: `${fa(overview?.tasks_total || 0)} کار کل` },
          ].map((s) => (
            <div key={s.l} className="card p-4">
              <p className="text-[11px] text-gray-500">{s.l}</p>
              <p className="mt-1.5 text-xl font-black text-white">{s.v}</p>
              <p className="mt-1 text-[10.5px] text-gray-500">{s.h}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2 text-xs">
          {[["tenants", "مشتری‌ها"], ["requests", `درخواست‌ها${overview?.pending_requests ? ` (${fa(overview.pending_requests)})` : ""}`], ["audit", "رخدادها"]].map(([k, l]) => (
            <button key={k} onClick={() => (k === "audit" ? openAudit() : setTab(k as any))}
              className={`rounded-xl px-4 py-2 font-medium transition ${tab === k ? "bg-brand-600 text-white" : "border border-white/10 bg-white/5 text-gray-300"}`}>
              {l}
            </button>
          ))}
          {tab === "tenants" && (
            <input className="input mr-auto !w-56 !py-1.5 text-xs" placeholder="جست‌وجوی نام یا شناسه…"
              value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
          )}
        </div>

        {tab === "tenants" && (
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-right text-[12.5px]">
              <thead className="border-b border-white/5 text-[11px] text-gray-500">
                <tr>
                  <th className="p-3">مشتری</th><th className="p-3">پلن</th><th className="p-3">وضعیت</th>
                  <th className="p-3">مصرف امروز</th><th className="p-3">توکن ماه</th><th className="p-3">عضویت</th><th className="p-3">اقدام</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {tenants.map((t) => (
                  <tr key={t.id} className="hover:bg-white/[0.02]">
                    <td className="p-3">
                      <p className="font-medium text-gray-100">{t.name}</p>
                      <p className="text-[10.5px] text-gray-500" dir="ltr">{t.owner_email || t.slug}</p>
                    </td>
                    <td className="p-3">
                      <select className="rounded-lg border border-white/10 bg-ink-900 px-2 py-1 text-[11.5px]" value={t.plan}
                        onChange={(e) => patch(t.id, { plan: e.target.value })}>
                        {Object.entries(PLAN_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                    </td>
                    <td className="p-3">
                      <span className={`chip ${STATUS_CLS[t.status]}`}>{STATUS_FA[t.status] || t.status}</span>
                      {t.trial_days_left != null && <span className="mr-1 text-[10px] text-gray-500">{fa(t.trial_days_left)} روز</span>}
                    </td>
                    <td className="p-3 text-gray-400">{fa(t.usage?.tasks_today || 0)} کار</td>
                    <td className="p-3 text-gray-400">{fa(t.usage?.tokens_month || 0)}</td>
                    <td className="p-3 text-gray-500">{fmtDate(t.created_at)}</td>
                    <td className="p-3">
                      <div className="flex gap-1.5">
                        {t.status === "suspended"
                          ? <button onClick={() => patch(t.id, { status: "active" })} className="chip bg-emerald-500/10 text-emerald-300">فعال‌سازی</button>
                          : <button onClick={() => patch(t.id, { status: "suspended", suspended_reason: "توقف توسط مدیر" })} className="chip bg-rose-500/10 text-rose-300">تعلیق</button>}
                        <button onClick={() => patch(t.id, { extend_trial_days: 7 })} className="chip bg-white/5 text-gray-300">+۷ روز</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {!tenants.length && <tr><td colSpan={7} className="p-6 text-center text-xs text-gray-500">مشتری‌ای یافت نشد</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        {tab === "requests" && (
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-right text-[12.5px]">
              <thead className="border-b border-white/5 text-[11px] text-gray-500">
                <tr><th className="p-3">تاریخ</th><th className="p-3">مشتری</th><th className="p-3">پلن</th><th className="p-3">مبلغ</th><th className="p-3">پیگیری</th><th className="p-3">وضعیت</th><th className="p-3">اقدام</th></tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {requests.map((r) => (
                  <tr key={r.id}>
                    <td className="p-3 text-gray-500">{fmtDate(r.created_at)}</td>
                    <td className="p-3 text-gray-200">{r.tenant}</td>
                    <td className="p-3 text-gray-300">{PLAN_FA[r.plan] || r.plan} · {fa(r.months)} ماه</td>
                    <td className="p-3 text-gray-200">{fa(r.amount_toman)} ت</td>
                    <td className="p-3 text-gray-500" dir="ltr">{r.reference || "—"}</td>
                    <td className="p-3"><span className={`chip ${STATUS_CLS[r.status]}`}>{STATUS_FA[r.status] || r.status}</span></td>
                    <td className="p-3">
                      {r.status === "pending" && (
                        <div className="flex gap-1.5">
                          <button onClick={() => decide(r.id, true)} className="chip bg-emerald-500/15 text-emerald-300">تأیید</button>
                          <button onClick={() => decide(r.id, false)} className="chip bg-rose-500/15 text-rose-300">رد</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {!requests.length && <tr><td colSpan={7} className="p-6 text-center text-xs text-gray-500">درخواستی ثبت نشده</td></tr>}
              </tbody>
            </table>
          </div>
        )}

        {tab === "audit" && (
          <div className="card p-0">
            <div className="max-h-[32rem] overflow-y-auto divide-y divide-white/5">
              {audit.map((a) => (
                <div key={a.id} className="flex items-start justify-between gap-3 p-3 text-[12px]">
                  <div>
                    <p className="font-medium text-gray-200">{a.action}</p>
                    <p className="mt-0.5 text-[10.5px] text-gray-500">{a.target} · {a.actor} {a.ip ? `· ${a.ip}` : ""}</p>
                  </div>
                  <span className="shrink-0 text-[10.5px] text-gray-500">{fmtDate(a.created_at)}</span>
                </div>
              ))}
              {!audit.length && <p className="p-6 text-center text-xs text-gray-500">رخدادی نیست</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
