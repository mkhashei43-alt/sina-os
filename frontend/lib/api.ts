"use client";

export const API = "";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("sina_token");
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) localStorage.setItem("sina_token", t);
  else localStorage.removeItem("sina_token");
}

export function getUser(): { id: string; email: string; name: string; role: string } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("sina_user");
  try { return raw ? JSON.parse(raw) : null; } catch { return null; }
}

export function setUser(u: any) {
  if (typeof window === "undefined") return;
  if (u) localStorage.setItem("sina_user", JSON.stringify(u));
  else localStorage.removeItem("sina_user");
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as any) };
  if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}/api${path}`, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
    setToken(null); setUser(null);
    location.href = "/login";
  }
  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return { detail: text }; } })() : null;
  if (!res.ok) {
    const msg = typeof data?.detail === "string" ? data.detail : JSON.stringify(data?.detail ?? data ?? "خطا");
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export function sseUrl(taskId: string) {
  const token = getToken() || "";
  return `${API}/api/tasks/${taskId}/events?token=${encodeURIComponent(token)}`;
}

export function fmtDate(d?: string | null) {
  if (!d) return "—";
  const dt = new Date(d);
  return new Intl.DateTimeFormat("fa-IR", { dateStyle: "short", timeStyle: "short" }).format(dt);
}

export function fmtBytes(n?: number) {
  if (!n) return "0";
  if (n < 1024) return `${n} بایت`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} کیلوبایت`;
  return `${(n / 1024 / 1024).toFixed(1)} مگابایت`;
}

export function fa(n?: number, digits = 0) {
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: digits }).format(n || 0);
}

export const STATUS_FA: Record<string, string> = {
  queued: "در صف", running: "در حال اجرا", waiting_approval: "در انتظار تأیید",
  completed: "تکمیل‌شده", failed: "ناموفق", cancelled: "لغوشده",
  ok: "موفق", error: "خطا", pending: "در انتظار", denied: "رد شده", blocked: "مسدود",
};

export const STATUS_COLOR: Record<string, string> = {
  queued: "bg-amber-500/15 text-amber-300",
  running: "bg-brand-500/15 text-brand-300",
  waiting_approval: "bg-orange-500/15 text-orange-300",
  completed: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-rose-500/15 text-rose-300",
  cancelled: "bg-gray-500/15 text-gray-300",
  ok: "bg-emerald-500/15 text-emerald-300",
  error: "bg-rose-500/15 text-rose-300",
};

export const TOOL_FA: Record<string, string> = {
  files: "مدیریت فایل", terminal: "ترمینال", python_exec: "اجرای پایتون",
  web_search: "جست‌وجوی وب", web_fetch: "دریافت صفحه", workspace: "فضای‌کار",
  system_monitor: "پایش سیستم", browser: "مرورگر", ssh: "SSH", github: "GitHub", cloudflare: "Cloudflare",
};
