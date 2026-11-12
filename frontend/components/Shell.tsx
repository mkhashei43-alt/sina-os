"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getToken, getUser, setToken, setUser } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "داشبورد", icon: "M3 12l9-9 9 9v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { href: "/chat", label: "گفتگو با سینا", icon: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" },
  { href: "/tasks", label: "کارها", icon: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" },
  { href: "/projects", label: "پروژه‌ها", icon: "M2 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" },
  { href: "/workspaces", label: "فضای‌کار", icon: "M3 7h18M3 12h18M3 17h18" },
  { href: "/files", label: "مدیریت فایل", icon: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6" },
  { href: "/terminal", label: "ترمینال", icon: "M4 17l6-5-6-5M12 19h8" },
  { href: "/browser", label: "مرورگر", icon: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20" },
  { href: "/memory", label: "حافظه", icon: "M12 2a7 7 0 0 1 7 7c0 3-2 5-3 7H8c-1-2-3-4-3-7a7 7 0 0 1 7-7zM9 21h6" },
  { href: "/integrations", label: "یکپارچه‌سازی", icon: "M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" },
  { href: "/models", label: "مدل‌ها", icon: "M12 2l3 7h7l-5.5 4.5L18 21l-6-4-6 4 1.5-7.5L2 9h7z" },
  { href: "/usage", label: "مصرف و هزینه", icon: "M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" },
  { href: "/logs", label: "لاگ فعالیت", icon: "M12 8v4l3 2M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z" },
  { href: "/system", label: "پایش سیستم", icon: "M22 12h-4l-3 9L9 3l-3 9H2" },
  { href: "/settings", label: "تنظیمات", icon: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9v.09a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z" },
  { href: "/subscription", label: "اشتراک و سهمیه", icon: "M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-7M2 7h20v5H2zM12 22V7" },
];

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.9"
      strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d={d} />
    </svg>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [user, setU] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    if (!getToken()) { router.replace("/login"); return; }
    setU(getUser());
    api("/health").then(setHealth).catch(() => {});
    const iv = setInterval(() => api("/health").then(setHealth).catch(() => setHealth({ status: "down" })), 30000);
    return () => clearInterval(iv);
  }, [router]);

  async function logout() {
    try { await api("/auth/logout", { method: "POST" }); } catch {}
    setToken(null); setUser(null); router.replace("/login");
  }

  return (
    <div className="flex min-h-screen">
      <aside className={`fixed inset-y-0 right-0 z-40 w-64 shrink-0 border-l border-white/5 bg-ink-900/95 backdrop-blur transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "translate-x-full lg:translate-x-0"}`}>
        <div className="flex h-16 items-center gap-3 border-b border-white/5 px-5">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-accent-500 text-lg shadow-glow">⚡</div>
          <div>
            <p className="text-sm font-black text-white">سینا AI OS</p>
            <p className="text-[10px] text-gray-500">عامل هوشمند خودمختار</p>
          </div>
        </div>
        <nav className="space-y-0.5 overflow-y-auto p-3" style={{ maxHeight: "calc(100vh - 8.5rem)" }}>
          {NAV.map((n) => {
            const active = path === n.href || path.startsWith(n.href + "/");
            return (
              <Link key={n.href} href={n.href} onClick={() => setOpen(false)}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition ${active ? "bg-gradient-to-l from-brand-600/25 to-accent-500/10 text-white shadow-[inset_0_0_0_1px_rgba(99,102,241,.25)]" : "text-gray-400 hover:bg-white/5 hover:text-gray-200"}`}>
                <Icon d={n.icon} />
                <span>{n.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="absolute bottom-0 w-full border-t border-white/5 p-3">
          {user?.platform_admin && (
            <Link href="/admin" className="mb-2 flex items-center justify-center rounded-xl border border-brand-500/30 bg-brand-500/10 px-3 py-2 text-[11.5px] font-medium text-brand-200 hover:bg-brand-500/20">
              پنل مدیریت پلتفرم
            </Link>
          )}
          <div className="flex items-center justify-between rounded-xl bg-white/5 px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-gray-200">{user?.name || user?.email || "کاربر"}</p>
              <p className="flex items-center gap-1 text-[10px] text-gray-500">
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${health?.status === "ok" ? "bg-emerald-400" : "bg-rose-400"}`} />
                {health?.status === "ok" ? "متصل" : "قطع"}
              </p>
            </div>
            <button onClick={logout} className="rounded-lg px-2 py-1 text-xs text-gray-400 hover:bg-white/10 hover:text-white">خروج</button>
          </div>
        </div>
      </aside>

      {open && <div className="fixed inset-0 z-30 bg-black/60 lg:hidden" onClick={() => setOpen(false)} />}

      <main className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-white/5 bg-ink-950/70 px-4 backdrop-blur lg:px-8">
          <button className="rounded-lg border border-white/10 p-2 lg:hidden" onClick={() => setOpen(true)}>☰</button>
          <div className="hidden items-center gap-2 text-xs text-gray-500 md:flex">
            <span className="chip bg-emerald-500/10 text-emerald-300">فعال</span>
            <span>سامانه در حال اجراست</span>
          </div>
          <div className="flex items-center gap-2">
            <Link href="/chat" className="btn-primary !py-2 text-xs">+ دستور جدید</Link>
          </div>
        </header>
        <div className="p-4 lg:p-8">{children}</div>
      </main>
    </div>
  );
}
