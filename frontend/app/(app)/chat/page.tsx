"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, fmtDate, getToken, sseUrl, TOOL_FA } from "@/lib/api";
import { Card, Empty, Spinner, StatusBadge, mdLite } from "@/components/ui";

type Msg = { role: string; content: string; task_id?: string; created_at?: string; id?: string };
type ToolEv = { tool: string; ok?: boolean; output?: string; duration_ms?: number; args?: any; running?: boolean };

export default function ChatPage() {
  const [convs, setConvs] = useState<any[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [live, setLive] = useState("");
  const [tools, setTools] = useState<ToolEv[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [approval, setApproval] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [uploadNote, setUploadNote] = useState("");
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => { loadConvs(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, live, tools]);

  async function loadConvs() {
    const list = await api<any[]>("/conversations").catch(() => []);
    setConvs(list);
    if (list.length && !convId) openConv(list[0].id);
  }

  async function openConv(id: string) {
    esRef.current?.close();
    setConvId(id); setLive(""); setTools([]); setTaskId(null); setStatus(""); setApproval(null);
    const d = await api(`/conversations/${id}/messages`).catch(() => null);
    if (!d) return;
    setMsgs(d.messages || []);
    const active = (d.tasks || []).find((t: any) => ["queued", "running", "waiting_approval"].includes(t.status));
    if (active) attach(active.id);
  }

  function attach(id: string) {
    esRef.current?.close();
    setTaskId(id); setStatus("running");
    const es = new EventSource(sseUrl(id));
    esRef.current = es;
    es.addEventListener("message.delta", (e: any) => { const d = JSON.parse(e.data); setLive((p) => p + (d.delta || "")); });
    es.addEventListener("tool.start", (e: any) => {
      const d = JSON.parse(e.data);
      setTools((p) => [...p, { tool: d.tool, args: d.args, running: true }]);
    });
    es.addEventListener("tool.end", (e: any) => {
      const d = JSON.parse(e.data);
      setTools((p) => {
        const idx = [...p].reverse().findIndex((t) => t.tool === d.tool && t.running);
        if (idx === -1) return [...p, { tool: d.tool, ok: d.ok, output: d.output, duration_ms: d.duration_ms }];
        const i = p.length - 1 - idx;
        const copy = [...p]; copy[i] = { ...copy[i], ...d, running: false }; return copy;
      });
    });
    es.addEventListener("task.status", (e: any) => { const d = JSON.parse(e.data); setStatus(d.status); });
    es.addEventListener("approval.request", (e: any) => setApproval(JSON.parse(e.data)));
    es.addEventListener("task.done", async (e: any) => {
      const d = JSON.parse(e.data);
      setStatus(d.status);
      es.close();
      setLive("");
      if (convId) {
        const r = await api(`/conversations/${convId}/messages`).catch(() => null);
        if (r) setMsgs(r.messages || []);
      }
      loadConvs();
    });
    es.onerror = () => { setStatus("disconnected"); es.close(); };
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true);
    try {
      let cid = convId;
      const body: any = { instruction: uploadNote ? `${text}\n\n[فایل پیوست: ${uploadNote}]` : text };
      if (cid) body.conversation_id = cid;
      const r = await api("/tasks", { method: "POST", body: JSON.stringify(body) });
      if (!cid) { cid = r.conversation_id; setConvId(cid); }
      setMsgs((p) => [...p, { role: "user", content: body.instruction, created_at: new Date().toISOString() }]);
      setInput(""); setUploadNote(""); setLive(""); setTools([]); setApproval(null);
      attach(r.task.id);
      loadConvs();
    } catch (e: any) {
      setMsgs((p) => [...p, { role: "assistant", content: `⚠️ خطا: ${e.message}` }]);
    } finally { setBusy(false); }
  }

  async function cancel() {
    if (!taskId) return;
    await api(`/tasks/${taskId}/cancel`, { method: "POST" }).catch(() => {});
    setStatus("cancelled");
  }

  async function decide(approve: boolean) {
    if (!taskId || !approval) return;
    const d = await api(`/tasks/${taskId}`, {}).catch(() => null);
    const ap = d?.approvals?.find((a: any) => a.status === "pending");
    if (!ap) { setApproval(null); return; }
    await api(`/tasks/${taskId}/approvals/${ap.id}`, { method: "POST", body: JSON.stringify({ approve }) });
    setApproval(null);
    attach(taskId);
  }

  async function upload(f: File) {
    const fd = new FormData();
    fd.append("file", f);
    const r = await api<any>("/uploads", { method: "POST", body: fd });
    setUploadNote(r.path);
  }

  const active = ["running", "queued", "waiting_approval"].includes(status);

  return (
    <div className="grid h-[calc(100vh-9rem)] gap-4 lg:grid-cols-[260px_1fr]">
      <Card className="hidden overflow-y-auto p-2 lg:block">
        <button onClick={() => { setConvId(null); setMsgs([]); }} className="btn-ghost mb-2 w-full text-xs">+ گفتگوی جدید</button>
        {convs.length === 0 && <p className="p-3 text-xs text-gray-500">هنوز گفتگویی نیست</p>}
        {convs.map((c) => (
          <button key={c.id} onClick={() => openConv(c.id)}
            className={`mb-1 w-full truncate rounded-lg px-3 py-2 text-right text-xs transition ${convId === c.id ? "bg-brand-600/20 text-white" : "text-gray-400 hover:bg-white/5"}`}>
            {c.title}
            <span className="mt-0.5 block text-[10px] text-gray-600">{fmtDate(c.updated_at)}</span>
          </button>
        ))}
      </Card>

      <Card className="flex min-h-0 flex-col overflow-hidden !p-0">
        <div className="flex items-center justify-between border-b border-white/5 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-500 text-sm">⚡</span>
            <div>
              <p className="text-sm font-bold text-white">سینا</p>
              <p className="text-[10px] text-gray-500">{status ? `وضعیت: ${status}` : "آماده دریافت دستور"}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {taskId && <Link href={`/tasks/${taskId}`} className="btn-ghost !py-1.5 text-[11px]">جزئیات کار</Link>}
            {active && <button onClick={cancel} className="btn-danger !py-1.5 text-[11px]">لغو</button>}
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {msgs.length === 0 && !live && <Empty text="دستور خود را بنویسید؛ سینا آن را برنامه‌ریزی و اجرا می‌کند." />}
          {msgs.map((m, i) => <Bubble key={m.id || i} m={m} />)}

          {(tools.length > 0 || live) && (
            <div className="space-y-2">
              {tools.map((t, i) => (
                <div key={i} className="rounded-xl border border-white/5 bg-ink-900/60 p-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs">
                      {t.running ? <Spinner size={12} /> : <span className={t.ok ? "text-emerald-400" : "text-rose-400"}>{t.ok ? "✓" : "✕"}</span>}
                      <span className="font-medium text-gray-200">{TOOL_FA[t.tool] || t.tool}</span>
                      {t.duration_ms != null && <span className="text-gray-500">{t.duration_ms}ms</span>}
                    </div>
                    <span className="mono text-[10px] text-gray-600" dir="ltr">{t.tool}</span>
                  </div>
                  {t.output && <pre dir="ltr" className="mono mt-2 max-h-32 overflow-auto rounded-lg bg-black/40 p-2 text-[11px] text-gray-400">{t.output.slice(0, 1500)}</pre>}
                </div>
              ))}
              {live && (
                <div className="rounded-xl border border-brand-500/20 bg-brand-600/10 p-3 text-sm text-gray-100">
                  <div className="prose-fa" dangerouslySetInnerHTML={mdLite(live)} />
                  <span className="inline-block h-3 w-1.5 animate-pulse bg-brand-400" />
                </div>
              )}
            </div>
          )}

          {approval && (
            <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 p-4">
              <p className="text-sm font-bold text-orange-200">⚠️ نیاز به تأیید شما</p>
              <p className="mt-1 text-xs text-orange-100/80">{approval.description}</p>
              <pre dir="ltr" className="mono mt-2 overflow-auto rounded-lg bg-black/30 p-2 text-[11px] text-orange-100/70">{JSON.stringify(approval.args, null, 2)}</pre>
              <div className="mt-3 flex gap-2">
                <button onClick={() => decide(true)} className="btn bg-emerald-600 text-white hover:bg-emerald-500">تأیید و ادامه</button>
                <button onClick={() => decide(false)} className="btn-ghost">رد عملیات</button>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-white/5 p-3">
          {uploadNote && (
            <div className="mb-2 flex items-center justify-between rounded-lg bg-accent-500/10 px-3 py-1.5 text-[11px] text-accent-400">
              <span>📎 {uploadNote}</span>
              <button onClick={() => setUploadNote("")} className="text-gray-400 hover:text-white">✕</button>
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea rows={1} value={input} onChange={(e) => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px"; }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
              className="input max-h-36 resize-none" placeholder="دستور خود را بنویسید… (Enter برای ارسال)" />
            <input ref={fileRef} type="file" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <button onClick={() => fileRef.current?.click()} className="btn-ghost shrink-0 !px-3" title="پیوست فایل">📎</button>
            <button onClick={send} disabled={busy || !input.trim()} className="btn-primary shrink-0">{busy ? <Spinner /> : "ارسال"}</button>
          </div>
        </div>
      </Card>
    </div>
  );
}

function Bubble({ m }: { m: Msg }) {
  const isUser = m.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${isUser ? "bg-white/5 text-gray-200" : "border border-brand-500/20 bg-gradient-to-l from-brand-600/15 to-accent-500/5 text-gray-100"}`}>
        <div className="prose-fa" dangerouslySetInnerHTML={mdLite(m.content)} />
        {m.created_at && <p className="mt-1 text-[10px] text-gray-500">{fmtDate(m.created_at)}</p>}
      </div>
    </div>
  );
}
