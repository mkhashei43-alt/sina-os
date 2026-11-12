"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Card, SectionTitle } from "@/components/ui";

export default function TerminalPage() {
  const [wss, setWss] = useState<any[]>([]);
  const [ws, setWs] = useState<string>("");
  const [lines, setLines] = useState<{ cmd?: string; out?: string; code?: number }[]>([]);
  const [cmd, setCmd] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams(location.search).get("ws");
    api<any[]>("/workspaces").then((l) => {
      setWss(l);
      const c = l.find((w) => w.id === qs) || l[0];
      if (c) setWs(c.id);
    });
  }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [lines]);

  async function run() {
    if (!cmd.trim() || !ws) return;
    const command = cmd;
    setCmd(""); setBusy(true);
    setLines((p) => [...p, { cmd: command }]);
    try {
      const r = await api(`/workspaces/${ws}/exec`, { method: "POST", body: JSON.stringify({ command, timeout: 60 }) });
      setLines((p) => [...p, { out: r.output, code: r.exit_code }]);
    } catch (e: any) {
      setLines((p) => [...p, { out: `⛔ ${e.message}`, code: 1 }]);
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <SectionTitle title="ترمینال" sub="اجرای دستورات در فضای‌کار ایزوله (دستورات پرخطر مسدود می‌شوند)"
        action={<select className="input max-w-xs" value={ws} onChange={(e) => setWs(e.target.value)}>
          {wss.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>} />

      <Card className="!p-0">
        <div dir="ltr" className="mono h-[62vh] overflow-y-auto bg-black/60 p-4 text-[12.5px]">
          <p className="text-gray-500">Sina AI OS — sandbox shell. Type a command below.</p>
          {lines.map((l, i) => (
            <div key={i} className="mt-2">
              {l.cmd && <p className="text-accent-400">$ {l.cmd}</p>}
              {l.out && <pre className={`log-line ${l.code === 0 ? "text-gray-300" : "text-rose-300"}`}>{l.out}</pre>}
            </div>
          ))}
          {busy && <p className="animate-pulse text-brand-400">▍ executing…</p>}
          <div ref={endRef} />
        </div>
        <div className="flex gap-2 border-t border-white/5 p-3">
          <span className="mono grid place-items-center px-2 text-accent-400">$</span>
          <input dir="ltr" className="input mono" placeholder="ls -la && python3 --version"
            value={cmd} onChange={(e) => setCmd(e.target.value)} onKeyDown={(e) => e.key === "Enter" && run()} />
          <button onClick={run} disabled={busy || !ws} className="btn-primary shrink-0 text-xs">اجرا</button>
        </div>
      </Card>
    </div>
  );
}
