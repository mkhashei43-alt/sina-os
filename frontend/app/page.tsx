"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, getToken, fa } from "@/lib/api";

type Plan = {
  key: string; name: string; price_toman: number; yearly_toman: number;
  tasks_per_day: number; tokens_per_month: number; workspaces: number; credentials: number;
  features: string[]; highlight: boolean; badge: string;
};

const FALLBACK_PLANS: Plan[] = [
  { key: "free", name: "رایگان", price_toman: 0, yearly_toman: 0, tasks_per_day: 10, tokens_per_month: 400000, workspaces: 2, credentials: 2, highlight: false, badge: "", features: ["۱۰ کار در روز", "۴۰۰ هزار توکن در ماه", "همهٔ ابزارهای پایه", "۲ فضای‌کار و ۲ اتصال"] },
  { key: "pro", name: "حرفه‌ای", price_toman: 890000, yearly_toman: 8900000, tasks_per_day: 150, tokens_per_month: 6000000, workspaces: 15, credentials: 12, highlight: true, badge: "پرفروش‌ترین", features: ["۱۵۰ کار در روز", "۶ میلیون توکن", "SSH، Cloudflare، GitHub، تلگرام", "۱۵ فضای‌کار و ۱۲ اتصال"] },
  { key: "business", name: "کسب‌وکار", price_toman: 2400000, yearly_toman: 24000000, tasks_per_day: 800, tokens_per_month: 30000000, workspaces: 60, credentials: 60, highlight: false, badge: "", features: ["۸۰۰ کار در روز", "۳۰ میلیون توکن", "همهٔ اتصال‌ها", "۶۰ فضای‌کار و ۶۰ اتصال"] },
];

const CAPS = [
  { icon: "💻", t: "کدنویسی و اجرا", d: "فایل می‌سازد، پایتون اجرا می‌کند، تست می‌نویسد و خطاها را خودش رفع می‌کند — تا وقتی خروجی درست بدهد." },
  { icon: "🖥️", t: "ورود به سرور (SSH)", d: "روی سرور خودتان دستور اجرا می‌کند، فایل می‌گذارد، سرویس را ری‌استارت می‌کند و لاگ می‌خواند." },
  { icon: "🌐", t: "Cloudflare", d: "رکورد DNS می‌سازد و تغییر می‌دهد، زون‌ها را می‌بیند و کش را پاک می‌کند." },
  { icon: "🐙", t: "GitHub", d: "ریپازیتوری می‌سازد، فایل کامیت می‌کند، ایشو و Pull Request باز می‌کند." },
  { icon: "✈️", t: "ربات تلگرام", d: "با ربات خودِ شما پیام و فایل می‌فرستد؛ گزارش‌ها را همان‌جا تحویل می‌دهد." },
  { icon: "🌍", t: "مرورگر و وب", d: "سایت را باز می‌کند، فرم پر می‌کند، اطلاعات لازم را از وب می‌آورد و خلاصه می‌کند." },
  { icon: "🧠", t: "حافظهٔ دائمی", d: "سلیقه، پروژه‌ها و تصمیم‌های شما را به یاد می‌آورد؛ هر بار از صفر شروع نمی‌کند." },
  { icon: "🛡️", t: "تأیید پیش از کار خطرناک", d: "هر عملی که ریسک دارد (حذف، تغییر سرور، ارسال پیام) قبل از اجرا از شما تأیید می‌گیرد." },
];

const STEPS = [
  { n: "۱", t: "ثبت‌نام در ۳۰ ثانیه", d: "فقط ایمیل و رمز. ۷ روز پلن حرفه‌ای رایگان، بدون کارت بانکی." },
  { n: "۲", t: "اتصال‌ها را وصل کنید", d: "سرور، Cloudflare، GitHub یا ربات تلگرام خودتان را با یک کلید وصل کنید — همه رمزنگاری‌شده ذخیره می‌شود." },
  { n: "۳", t: "به فارسی بگویید چه می‌خواهید", d: "«روی سرورم nginx را آپدیت کن و ساب‌دامین بساز» — سینا خودش برنامه می‌ریزد و انجام می‌دهد." },
  { n: "۴", t: "خروجی را تحویل بگیرید", d: "گزارش کامل با تمام مراحل، دستورها و فایل‌های ساخته‌شده — قابل بازبینی و قابل ادامه." },
];

const FAQ = [
  { q: "کلیدها و اطلاعات سرور من امن است؟", a: "بله. هر کلید با Fernet رمزنگاری و در دیتابیس ذخیره می‌شود، هیچ‌وقت به مدل زبانی فرستاده نمی‌شود و در لاگ‌ها ماسک است. هر مشتری فقط کلیدهای خودش را می‌بیند." },
  { q: "سینا چه کارهایی را بدون اجازه انجام می‌دهد؟", a: "خواندن فایل، اجرای محاسبه، جست‌وجوی وب و ساخت فایل در فضای‌کار خودکار انجام می‌شود. دستورهای تغییردهنده روی سرور، DNS، کامیت گیت‌هاب و ارسال پیام تلگرام پشت دروازهٔ تأیید شما هستند." },
  { q: "اگر کارها زیاد باشد چه می‌شود؟", a: "سهمیهٔ پلن شما در داشبورد شفاف است (کارهای امروز و توکن‌های این ماه). می‌توانید پلن را ارتقا دهید یا کلید OpenRouter خودتان را وصل کنید تا مصرف از اعتبار خودتان باشد." },
  { q: "می‌توانم روزها کار را ادامه دهم؟", a: "بله. هر کار در دیتابیس ذخیره می‌شود؛ اگر سرور ری‌استارت شود یا اتصال قطع شود، کار از همان نقطه ادامه پیدا می‌کند." },
  { q: "روش پرداخت چطور است؟", a: "پلن را انتخاب می‌کنید، درخواست ثبت می‌شود و پس از واریز (کارت‌به‌کارت) با تأیید مدیر فعال می‌شود. فاکتور در داشبورد قابل مشاهده است." },
];

export default function Landing() {
  const [meta, setMeta] = useState<any>(null);
  const [plans, setPlans] = useState<Plan[]>(FALLBACK_PLANS);
  const [yearly, setYearly] = useState(false);

  useEffect(() => {
    if (getToken()) { location.replace("/dashboard"); return; }
    api("/public/meta").then((m) => {
      setMeta(m);
      if (m?.plans?.length) setPlans(m.plans);
    }).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen">
      {/* nav */}
      <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-950/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-lg shadow-glow">⚡</span>
            <span className="text-sm font-black text-white">{meta?.brand || "سینا کلود"}</span>
          </Link>
          <nav className="hidden items-center gap-6 text-[13px] text-gray-400 md:flex">
            <a href="#features" className="hover:text-white">امکانات</a>
            <a href="#how" className="hover:text-white">نحوهٔ کار</a>
            <a href="#pricing" className="hover:text-white">تعرفه</a>
            <a href="#faq" className="hover:text-white">سؤالات</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link href="/login" className="btn-ghost !py-2 text-xs">ورود</Link>
            <Link href="/signup" className="btn-primary !py-2 text-xs">شروع رایگان</Link>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 md:grid-cols-2 md:py-24">
          <div className="flex flex-col justify-center">
            <span className="chip mb-5 w-fit bg-brand-500/10 text-brand-300">✨ {meta?.trial_days || 7} روز رایگان — بدون کارت بانکی</span>
            <h1 className="text-3xl font-black leading-[1.35] text-white md:text-[2.6rem]">
              کارمند هوشمندی که
              <span className="bg-gradient-to-l from-brand-400 to-accent-400 bg-clip-text text-transparent"> خودش کار می‌کند</span>
            </h1>
            <p className="mt-5 text-[15px] leading-8 text-gray-400">
              به سینا بگویید چه می‌خواهید؛ خودش برنامه می‌ریزد، فایل می‌سازد، کد اجرا می‌کند،
              <b className="text-gray-200"> به سرورتان SSH می‌زند</b>، در Cloudflare دامنه می‌سازد،
              در GitHub کامیت می‌کند و نتیجه را در تلگرام تحویل می‌دهد.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href="/signup" className="btn-primary px-6 py-3 text-sm">شروع رایگان</Link>
              <a href="#pricing" className="btn-ghost px-6 py-3 text-sm">دیدن تعرفه‌ها</a>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-gray-500">
              <span>✓ بدون نیاز به دانش فنی</span>
              <span>✓ کلیدها رمزنگاری‌شده</span>
              <span>✓ تأیید پیش از کارهای خطرناک</span>
            </div>
          </div>

          {/* fake terminal */}
          <div className="relative">
            <div className="card overflow-hidden p-0 shadow-glow">
              <div className="flex items-center gap-1.5 border-b border-white/5 bg-white/[0.03] px-4 py-3">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500/70" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
                <span className="mr-auto text-[11px] text-gray-500">sina · agent log</span>
              </div>
              <div className="space-y-3 p-5 text-[12.5px] leading-7">
                <p className="text-gray-300">‹ <span className="text-white">«سرورم را چک کن و nginx را آپدیت کن»</span></p>
                <div className="space-y-1.5 border-r-2 border-brand-500/40 pr-3 text-gray-400">
                  <p><span className="text-accent-400">تحلیل</span> · نیاز به SSH + ترمینال + تأیید تغییر سرویس</p>
                  <p><span className="text-accent-400">برنامه</span> · ۴ گام: بررسی وضعیت → بکاپ کانفیگ → آپدیت → تست سلامت</p>
                  <p><span className="text-emerald-400">اجرا</span> · ssh · uptime → load 1.4 ✓</p>
                  <p><span className="text-emerald-400">اجرا</span> · systemctl restart nginx ✓</p>
                  <p><span className="text-amber-400">تأیید</span> · تغییر کانفیگ nginx → منتظر اجازهٔ شما</p>
                </div>
                <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-emerald-300">✓ سرور سالم است؛ گزارش کامل در تلگرام ارسال شد.</p>
              </div>
            </div>
            <div className="pointer-events-none absolute -inset-6 -z-10 bg-brand-500/10 blur-3xl" />
          </div>
        </div>

        {/* stats */}
        <div className="mx-auto grid max-w-6xl grid-cols-3 gap-4 px-4 pb-12">
          {[
            { k: fa(meta?.stats?.customers || 0), l: "حساب فعال" },
            { k: fa(meta?.stats?.tasks || 0), l: "کار اجراشده" },
            { k: "۲۴/۷", l: "در دسترس" },
          ].map((s) => (
            <div key={s.l} className="card px-4 py-5 text-center">
              <p className="text-xl font-black text-white">{s.k}</p>
              <p className="mt-1 text-[11px] text-gray-500">{s.l}</p>
            </div>
          ))}
        </div>
      </section>

      {/* features */}
      <section id="features" className="mx-auto max-w-6xl px-4 py-16">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-black text-white">هر چیزی بگویید؛ انجام می‌دهد</h2>
          <p className="mt-3 text-sm text-gray-400">همهٔ این‌ها با کلیدها و حساب‌های خودِ شما اجرا می‌شود</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CAPS.map((c) => (
            <div key={c.t} className="card card-hover p-5">
              <div className="mb-3 grid h-11 w-11 place-items-center rounded-xl bg-white/5 text-xl">{c.icon}</div>
              <h3 className="text-sm font-bold text-white">{c.t}</h3>
              <p className="mt-2 text-[12.5px] leading-6 text-gray-400">{c.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* how */}
      <section id="how" className="border-y border-white/5 bg-white/[0.015] py-16">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="mb-10 text-center text-2xl font-black text-white">در چهار قدم شروع کنید</h2>
          <div className="grid gap-4 md:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.n} className="card p-5">
                <span className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-brand-600 to-accent-500 text-sm font-black text-white">{s.n}</span>
                <h3 className="mt-4 text-sm font-bold text-white">{s.t}</h3>
                <p className="mt-2 text-[12.5px] leading-6 text-gray-400">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* pricing */}
      <section id="pricing" className="mx-auto max-w-6xl px-4 py-16">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-black text-white">تعرفهٔ شفاف، بدون هزینهٔ پنهان</h2>
          <p className="mt-3 text-sm text-gray-400">{meta?.trial_days || 7} روز اول با سهمیهٔ پلن حرفه‌ای، رایگان</p>
          <div className="mt-5 inline-flex rounded-xl border border-white/10 bg-white/5 p-1 text-xs">
            <button onClick={() => setYearly(false)} className={`rounded-lg px-4 py-1.5 ${!yearly ? "bg-brand-600 text-white" : "text-gray-400"}`}>ماهانه</button>
            <button onClick={() => setYearly(true)} className={`rounded-lg px-4 py-1.5 ${yearly ? "bg-brand-600 text-white" : "text-gray-400"}`}>سالانه (۲ ماه هدیه)</button>
          </div>
        </div>
        <div className="grid gap-5 md:grid-cols-3">
          {plans.map((p) => (
            <div key={p.key} className={`card relative flex flex-col p-6 ${p.highlight ? "border-brand-500/40 shadow-glow" : ""}`}>
              {p.badge && <span className="absolute -top-3 right-6 chip bg-gradient-to-l from-brand-600 to-accent-500 text-white">{p.badge}</span>}
              <h3 className="text-lg font-black text-white">{p.name}</h3>
              <div className="mt-3 flex items-end gap-1">
                <span className="text-2xl font-black text-white">{p.price_toman ? fa(yearly ? p.yearly_toman : p.price_toman) : "۰"}</span>
                <span className="mb-1 text-xs text-gray-500">تومان / {yearly ? "سال" : "ماه"}</span>
              </div>
              <ul className="mt-5 flex-1 space-y-2.5 text-[12.5px] text-gray-300">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2"><span className="text-emerald-400">✓</span><span>{f}</span></li>
                ))}
              </ul>
              <Link href={`/signup?plan=${p.key}`} className={`mt-6 w-full ${p.highlight ? "btn-primary" : "btn-ghost"} py-2.5 text-sm`}>
                {p.price_toman ? "شروع کنید" : "شروع رایگان"}
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-[11px] text-gray-500">برای تیم‌های بزرگ‌تر و استقرار اختصاصی، از طریق فرم پایین صفحه تماس بگیرید.</p>
      </section>

      {/* faq */}
      <section id="faq" className="border-t border-white/5 bg-white/[0.015] py-16">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="mb-8 text-center text-2xl font-black text-white">سؤالات پرتکرار</h2>
          <div className="space-y-3">
            {FAQ.map((f) => (
              <details key={f.q} className="card group px-5 py-4">
                <summary className="cursor-pointer list-none text-sm font-medium text-gray-200 marker:hidden">
                  <span className="ml-2 inline-block text-brand-400 transition group-open:rotate-90">›</span>{f.q}
                </summary>
                <p className="mt-3 text-[12.5px] leading-7 text-gray-400">{f.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* cta */}
      <section className="mx-auto max-w-5xl px-4 py-16">
        <div className="card relative overflow-hidden bg-gradient-to-l from-brand-600/20 to-accent-500/10 p-10 text-center">
          <h2 className="text-2xl font-black text-white">امروز کارهای تکراری را به سینا بسپارید</h2>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-gray-300">
            ثبت‌نام کنید، کلیدها را وصل کنید و اولین کار را بسپارید. اگر جواب نداد، پول برنمی‌گردانیم — چون رایگان است.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <Link href="/signup" className="btn-primary px-7 py-3">شروع رایگان</Link>
            {meta?.support_telegram && <a href={`https://t.me/${meta.support_telegram}`} className="btn-ghost px-7 py-3">گفتگو با فروش</a>}
          </div>
        </div>
      </section>

      <footer className="border-t border-white/5 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 text-[11px] text-gray-500 md:flex-row">
          <p>© {new Date().getFullYear()} {meta?.brand || "سینا کلود"} — دستیار هوشمند اجرایی</p>
          <div className="flex gap-4">
            <Link href="/login" className="hover:text-gray-300">ورود</Link>
            <Link href="/signup" className="hover:text-gray-300">ثبت‌نام</Link>
            <a href="#pricing" className="hover:text-gray-300">تعرفه</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
