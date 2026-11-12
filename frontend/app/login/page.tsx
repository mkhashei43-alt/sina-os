"use client";
import { useState } from "react";
import { api, setToken, setUser } from "@/lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("admin@sina.local");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const r = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setToken(r.access_token); setUser(r.user);
      location.href = "/dashboard";
    } catch (e: any) {
      setErr(e.message || "ورود ناموفق بود");
    } finally { setBusy(false); }
  }

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-3xl bg-gradient-to-br from-brand-500 to-accent-500 text-3xl shadow-glow">⚡</div>
          <h1 className="text-2xl font-black text-white">سینا AI OS</h1>
          <p className="mt-2 text-sm text-gray-400">سیستم‌عامل شخصیِ خودمختار هوش مصنوعی</p>
        </div>
        <form onSubmit={submit} className="card space-y-4 p-7">
          <div>
            <label className="label">ایمیل</label>
            <input className="input" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
          </div>
          <div>
            <label className="label">رمز عبور</label>
            <input className="input" dir="ltr" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          {err && <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-xs text-rose-300">{err}</p>}
          <button disabled={busy} className="btn-primary w-full py-3">{busy ? "در حال ورود…" : "ورود به داشبورد"}</button>
          <p className="text-center text-[11.5px] text-gray-400">
            حساب ندارید؟ <a href="/signup" className="text-brand-300 hover:text-brand-200">ساخت حساب رایگان</a>
          </p>
        </form>
      </div>
    </div>
  );
}
