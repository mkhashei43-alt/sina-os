"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Card, Modal, SectionTitle } from "@/components/ui";

type Provider = {
  key: string; name: string; category: string; fields: string[];
  docs: string; actions: Record<string, any>; note: string;
};

const ICONS: Record<string, string> = {
  ai: "🧠", search: "🔎", messaging: "💬", email: "✉️", dev: "🛠️",
  infra: "🖥️", productivity: "🗂️", social: "🌍", commerce: "🛒", data: "📊",
};

export default function IntegrationsPage() {
  const [catalog, setCatalog] = useState<Provider[]>([]);
  const [categories, setCategories] = useState<Record<string, string>>({});
  const [items, setItems] = useState<Record<string, any>>({});
  const [edit, setEdit] = useState<Provider | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");

  const load = () => api<Record<string, any>>("/integrations").then(setItems).catch(() => {});
  useEffect(() => {
    load();
    api<{ providers: Provider[]; categories: Record<string, string> }>("/integrations/catalog")
      .then((d) => { setCatalog(d.providers); setCategories(d.categories); })
      .catch(() => {});
  }, []);

  const list = useMemo(() => catalog.filter((p) =>
    (!cat || p.category === cat) &&
    (!q || p.name.toLowerCase().includes(q.toLowerCase()) || p.key.includes(q.toLowerCase()))
  ), [catalog, q, cat]);

  function open(p: Provider) { setEdit(p); setForm({}); setMsg(""); }

  async function save() {
    if (!edit) return;
    try {
      await api("/integrations", { method: "POST", body: JSON.stringify({ kind: edit.key, config: form, enabled: true }) });
      setEdit(null); load();
    } catch (e: any) { setMsg(e.message); }
  }
  async function remove(kind: string) { await api(`/integrations/${kind}`, { method: "DELETE" }); load(); }

  const connectedCount = Object.values(items).filter((i: any) => i?.configured).length;

  return (
    <div className="space-y-5">
      <SectionTitle
        title="اتصال‌ها"
        sub={`کلید خودتان را بدهید؛ ${catalog.length || 73} سرویس پشتیبانی می‌شود. اطلاعات حساس رمزنگاری و ماسک می‌شود.`}
      />

      <div className="flex flex-wrap items-center gap-2">
        <input className="input !w-64" placeholder="جست‌وجوی سرویس…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input !w-52" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="">همهٔ دسته‌ها</option>
          {Object.entries(categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span className="chip bg-emerald-500/10 text-emerald-300">{connectedCount} متصل</span>
        <span className="text-[11px] text-gray-500">{list.length} سرویس</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {list.map((p) => {
          const it = items[p.key];
          const on = it?.configured;
          return (
            <Card key={p.key} className={`card-hover ${on ? "border-emerald-500/25" : ""}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-white/5 text-xl">{ICONS[p.category] || "🔌"}</div>
                  <div>
                    <h3 className="font-bold text-white">{p.name}</h3>
                    <p className="text-[10.5px] text-gray-500" dir="ltr">{p.key}</p>
                  </div>
                </div>
                <span className={`chip ${on ? "bg-emerald-500/10 text-emerald-300" : "bg-gray-500/10 text-gray-400"}`}>
                  {on ? "متصل" : "خالی"}
                </span>
              </div>
              <p className="mt-3 min-h-[2.2rem] text-[11.5px] leading-6 text-gray-400">
                {Object.keys(p.actions || {}).length ? `عملیات: ${Object.keys(p.actions).slice(0, 3).join("، ")}` : "دسترسی عمومی REST"}
                {p.note ? ` — ${p.note}` : ""}
              </p>
              <div className="mt-3 flex gap-2">
                <button onClick={() => open(p)} className="btn-ghost flex-1 !py-1.5 text-xs">
                  {on ? "ویرایش" : "افزودن کلید"}
                </button>
                {on && <button onClick={() => remove(p.key)} className="btn-danger !py-1.5 text-xs">حذف</button>}
                <a href={p.docs} target="_blank" rel="noopener" className="btn-ghost !py-1.5 text-xs">راهنما ↗</a>
              </div>
            </Card>
          );
        })}
      </div>

      <Modal open={!!edit} onClose={() => setEdit(null)} title={`کلید ${edit?.name || ""}`}>
        {edit && (
          <div className="space-y-3">
            {edit.fields.filter((f) => f !== "none").map((f) => (
              <div key={f}>
                <label className="label mono" dir="ltr">
                  {f}{items[edit.key]?.fields_configured?.includes(f) ? " ✓" : ""}
                </label>
                <input
                  className="input" dir="ltr"
                  type={/key|token|secret|password|dsn|sid/i.test(f) ? "password" : "text"}
                  placeholder={items[edit.key]?.fields_configured?.includes(f) ? "مقدار جدید (خالی = بدون تغییر)" : ""}
                  value={form[f] || ""} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
              </div>
            ))}
            {msg && <p className="text-xs text-rose-300">{msg}</p>}
            <p className="text-[11px] leading-6 text-gray-500">
              مقادیر با کلید رمزنگاری همین دستگاه ذخیره می‌شوند و هرگز در پاسخ API یا لاگ نمایش داده نمی‌شوند.
              {edit.note ? ` ${edit.note}` : ""}
            </p>
            <button onClick={save} className="btn-primary w-full">ذخیره</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
