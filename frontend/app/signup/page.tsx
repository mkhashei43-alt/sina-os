"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, setToken, setUser } from "@/lib/api";

export default function SignupPage() {
  const [form, setForm] = useState({ name: "", company: "", email: "", password: "" });
  const [plan, setPlan] = useState("trial");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [social, setSocial] = useState<any>(null);

  useEffect(() => {
    const p = new URLSearchParams(location.search).get("plan");
    if (p) setPlan(p);
    api("/public/meta").then(setSocial).catch(() => {});
  }, []);

  function set(k: string, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await api("/public/signup", {
        method: "POST",
        body: JSON.stringify({ ...form, plan, accept_terms: true }),
      });
      setToken(r.access_token);
      setUser(r.user);
      location.href = "/dashboard?welcome=1";
    } catch (e: any) {
      setErr(typeof e.message === "string" ? e.message : "ثبت‌نام ناموفق بود");
    } finally { setBusy(false); }
  }

  const strength = form.password.length >= 12 ? 3 : form.password.length >= 9 ? 2 : form.password.length >= 6 ? 1 : 0;

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-7 flex items-center justify-center gap-2.5">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-accent-500 text-xl shadow-glow">⚡</span>
          <span className="text-lg font-black text-white">{social?.brand || "سینا کلود"}</span>
        </Link>

        <form onSubmit={submit} className="card space-y-4 p-7">
          <div className="text-center">
            <h1 className="text-lg font-black text-white">ساخت حساب</h1>
            <p className="mt-1.5 text-[11.5px] text-gray-400">
              {social?.trial_days || 7} روز پلن حرفه‌ای رایگان · بدون کارت بانکی
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">نام و نام خانوادگی</label>
              <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} required />
            </div>
            <div>
              <label className="label">نام کسب‌وکار (اختیاری)</label>
              <input className="input" value={form.company} onChange={(e) => set("company", e.target.value)} placeholder="مثلاً فروشگاه من" />
            </div>
          </div>

          <div>
            <label className="label">ایمیل</label>
            <input className="input" dir="ltr" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required autoComplete="username" />
          </div>

          <div>
            <label className="label">رمز عبور</label>
            <input className="input" dir="ltr" type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required minLength={8} autoComplete="new-password" />
            <div className="mt-2 flex gap-1">
              {[1, 2, 3].map((i) => (
                <span key={i} className={`h-1 flex-1 rounded-full ${strength >= i ? (strength === 3 ? "bg-emerald-500" : strength === 2 ? "bg-amber-500" : "bg-rose-500") : "bg-white/10"}`} />
              ))}
            </div>
            <p className="mt-1 text-[10.5px] text-gray-500">حداقل ۸ کاراکتر — ترکیبی از حرف و عدد</p>
          </div>

          {err && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs leading-6 text-rose-300">{err}</p>}

          <button disabled={busy} className="btn-primary w-full py-3">
            {busy ? "در حال ساخت حساب…" : "شروع دورهٔ رایگان"}
          </button>

          <p className="text-center text-[10.5px] leading-5 text-gray-500">
            با ثبت‌نام، شرایط استفاده و سیاست حفظ حریم خصوصی را می‌پذیرید.
            کلیدهای شما فقط برای اجرای کارهای خودتان استفاده می‌شود.
          </p>

          <p className="text-center text-[11.5px] text-gray-400">
            حساب دارید؟ <Link href="/login" className="text-brand-300 hover:text-brand-200">ورود</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
