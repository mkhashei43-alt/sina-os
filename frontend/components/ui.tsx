"use client";
import React from "react";
import { STATUS_COLOR, STATUS_FA } from "@/lib/api";

export function Card({ className = "", children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`card p-5 ${className}`} {...rest}>{children}</div>;
}

export function SectionTitle({ title, sub, action }: { title: string; sub?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-5 flex items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-white">{title}</h1>
        {sub && <p className="mt-1 text-sm text-gray-400">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLOR[status] || "bg-gray-500/15 text-gray-300";
  const label = STATUS_FA[status] || status;
  return (
    <span className={`chip ${cls}`}>
      {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {label}
    </span>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="animate-spin text-brand-400">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" fill="none" opacity=".25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export function Empty({ text, icon }: { text: string; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-14 text-center text-gray-500">
      <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/5 bg-white/5">{icon || "✦"}</div>
      <p className="text-sm">{text}</p>
    </div>
  );
}

export function Meter({ label, percent, detail }: { label: string; percent: number; detail?: string }) {
  const p = Math.max(0, Math.min(100, percent || 0));
  const color = p > 85 ? "bg-rose-500" : p > 65 ? "bg-amber-500" : "bg-gradient-to-l from-brand-500 to-accent-500";
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="font-mono text-gray-300">{p.toFixed(1)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${p}%` }} />
      </div>
      {detail && <p className="mt-1 text-[11px] text-gray-500">{detail}</p>}
    </div>
  );
}

export function Stat({ label, value, hint, accent }: { label: string; value: React.ReactNode; hint?: string; accent?: string }) {
  return (
    <Card className="card-hover">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${accent || "text-white"}`}>{value}</p>
      {hint && <p className="mt-1 text-[11px] text-gray-500">{hint}</p>}
    </Card>
  );
}

export function Modal({ open, onClose, title, children, wide }: any) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className={`card w-full ${wide ? "max-w-3xl" : "max-w-lg"} p-6`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Code({ children, className = "", max = "max-h-72" }: { children: React.ReactNode; className?: string; max?: string }) {
  return (
    <pre dir="ltr" className={`mono ${max} overflow-auto rounded-xl border border-white/5 bg-ink-950/80 p-3 text-gray-300 ${className}`}>
      {children}
    </pre>
  );
}

export function mdLite(text: string) {
  // minimal safe markdown: bold, inline code, code fences, bullets, links
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  let html = esc(text || "");
  html = html.replace(/```([\s\S]*?)```/g, (_m, c) => `<pre>${c}</pre>`);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/^### (.*)$/gm, "<h3>$1</h3>").replace(/^## (.*)$/gm, "<h2>$1</h2>").replace(/^# (.*)$/gm, "<h1>$1</h1>");
  html = html.replace(/^\s*[-*] (.*)$/gm, "<li>$1</li>").replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>");
  html = html.replace(/(https?:\/\/[^\s<")]+)/g, '<a href="$1" target="_blank" rel="noreferrer" class="text-accent-400 underline">$1</a>');
  html = html.replace(/\n/g, "<br/>");
  return { __html: html };
}
