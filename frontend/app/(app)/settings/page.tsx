"use client";
import { useEffect, useState } from "react";
import { api, getUser } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";

export default function SettingsPage() {
  const [s, setS] = useState<any>(null);
  const [pw, setPw] = useState({ current: "", next: "" });
  const [msg, setMsg] = useState("");
  const u = typeof window !== "undefined" ? getUser() : null;

  useEffect(() => { api("/settings").then(setS).catch(() => {}); }, []);

  return (
    <div className="space-y-5">
      <SectionTitle title="تنظیمات" sub="پیکربندی سیستم، محدودیت‌ها و حساب کاربری" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">حساب کاربری</h3>
          <div className="space-y-2 text-xs text-gray-400">
            <p>نام: <span className="text-gray-200">{u?.name || "—"}</span></p>
            <p>ایمیل: <span className="mono text-gray-200" dir="ltr">{u?.email}</span></p>
            <p>نقش: <span className="text-gray-200">{u?.role}</span></p>
          </div>
          <div className="mt-4 space-y-2">
            <input type="password" className="input" placeholder="رمز فعلی" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
            <input type="password" className="input" placeholder="رمز جدید" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
            <button onClick={async () => { try { await api("/auth/password", { method: "POST", body: JSON.stringify(pw) }); setMsg("رمز تغییر کرد ✓"); } catch (e: any) { setMsg(e.message); } }}
              className="btn-ghost w-full text-xs">تغییر رمز</button>
            {msg && <p className="text-[11px] text-accent-400">{msg}</p>}
          </div>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">وضعیت سامانه</h3>
          <div className="space-y-2 text-xs">
            <Row k="محیط" v={s?.app?.env} />
            <Row k="کلید OpenRouter" v={s?.provider_configured ? "تنظیم شده" : "تنظیم نشده"} />
            <Row k="ربات تلگرام" v={s?.telegram_configured ? "تنظیم شده" : "تنظیم نشده"} />
            <Row k="مدل پیش‌فرض" v={s?.models?.default} mono />
            <Row k="مدل کدنویسی" v={s?.models?.coding} mono />
            <Row k="مدل استدلال" v={s?.models?.reasoning} mono />
          </div>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">محدودیت‌ها و سیاست امنیتی</h3>
          <div className="space-y-2 text-xs">
            <Row k="مهلت اجرای دستور" v={`${s?.limits?.exec_timeout} ثانیه`} />
            <Row k="حداکثر حجم آپلود" v={`${s?.limits?.max_upload_mb} مگابایت`} />
            <Row k="حداکثر گام‌های عامل" v={s?.limits?.max_agent_iterations} />
            <Row k="حداکثر فراخوانی ابزار" v={s?.limits?.max_tool_calls} />
            <Row k="سطوح نیازمند تأیید" v={(s?.limits?.approval_levels || []).join(", ")} />
          </div>
          <h3 className="mb-2 mt-5 text-sm font-bold text-white">بسته‌های مجاز pip</h3>
          <div className="flex flex-wrap gap-1">
            {(s?.pip_allowlist || []).map((p: string) => <span key={p} className="chip bg-white/5 text-gray-300 mono" dir="ltr">{p}</span>)}
          </div>
        </Card>

        <Card>
          <h3 className="mb-3 text-sm font-bold text-white">درباره</h3>
          <p className="text-xs leading-6 text-gray-400">
            سینا AI OS — سیستم‌عامل شخصی خودمختار هوش مصنوعی. همه عملیات با ابزارهای واقعی اجرا و در لاگ ثبت می‌شوند.
            عملیات پرخطر نیازمند تأیید صریح شما هستند و کلیدها هرگز در خروجی نمایش داده نمی‌شوند.
          </p>
          <p className="mono mt-3 text-[10px] text-gray-600" dir="ltr">Sina AI OS v1.0.0</p>
        </Card>
      </div>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: any; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-white/5 py-1.5 last:border-0">
      <span className="text-gray-500">{k}</span>
      <span className={`text-gray-200 ${mono ? "mono" : ""}`} dir={mono ? "ltr" : "rtl"}>{v || "—"}</span>
    </div>
  );
}
