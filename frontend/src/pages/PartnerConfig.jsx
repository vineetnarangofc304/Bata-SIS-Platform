import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, Plus } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { PageHeader, Field, inputCls, selectCls } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";

const LISTS = ["keywords", "sender_domains", "sender_emails", "subject_patterns", "expected_columns"];

export default function PartnerConfig() {
  const [partners, setPartners] = useState([]);
  const [sel, setSel] = useState(null);
  const [form, setForm] = useState(null);
  const [stats, setStats] = useState(null);
  const [mappings, setMappings] = useState([]);
  const load = () => api.get("/partners").then((r) => { setPartners(r.data); if (!sel && r.data.length) pick(r.data[0]); });
  useEffect(() => { load(); }, []); // eslint-disable-line
  const pick = (p) => { setSel(p); setForm({ ...p, ...Object.fromEntries(LISTS.map((k) => [k, (p[k] || []).join(", ")])), contact_name: p.contact?.name || "", contact_email: p.contact?.email || "" }); api.get(`/partners/${p.code}/stats`).then((r) => setStats(r.data)); api.get(`/partners/${p.code}/mappings`).then((r) => setMappings(r.data)); };
  const save = async () => {
    const body = { ...form, contact: { name: form.contact_name, email: form.contact_email } };
    LISTS.forEach((k) => { body[k] = String(form[k] || "").split(",").map((s) => s.trim()).filter(Boolean); });
    delete body.contact_name; delete body.contact_email;
    try { if (body.id) await api.put(`/masters/partners/${body.id}`, body); else await api.post("/masters/partners", body); toast.success("Partner configuration saved (versioned)"); const r = await api.get("/partners"); setPartners(r.data); const p = r.data.find((x) => x.code === body.code); if (p) pick(p); } catch (e) { toast.error(errMsg(e)); }
  };
  const f = (k, label, type = "text", opts) => <Field label={label}>{opts ? <select data-testid={`partner-form-${k}`} value={String(form[k] ?? "")} onChange={(e) => setForm({ ...form, [k]: opts.bool ? e.target.value === "true" : e.target.value })} className={selectCls}>{opts.items.map((o) => <option key={String(o.v)} value={String(o.v)}>{o.l}</option>)}</select> : <input data-testid={`partner-form-${k}`} type={type} value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className={inputCls} />}</Field>;
  return (
    <div data-testid="partner-config-page">
      <PageHeader title="Partner Configuration" sub="9 configurable SIS partners. Recognition keywords, sender rules, ingestion policy and learned mapping versions per partner." actions={<button data-testid="partner-add-btn" onClick={() => { setSel({}); setForm({ code: "", name: "", active: true, partial_ingestion: true, expected_frequency: "daily", keywords: "", sender_domains: "", sender_emails: "", subject_patterns: "", expected_columns: "", contact_name: "", contact_email: "", notes: "" }); setStats(null); setMappings([]); }} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Plus className="h-3.5 w-3.5" />New partner</button>} />
      <div className="grid lg:grid-cols-[260px_1fr] gap-5">
        <div className="card p-2 h-fit" data-testid="partner-list">{partners.map((p) => <button key={p.code} data-testid={`partner-item-${p.code}`} onClick={() => pick(p)} className={`w-full text-left px-3 py-2 rounded flex items-center justify-between ${sel?.code === p.code ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}><span><span className="font-mono text-xs opacity-60 mr-2">{p.code}</span><span className="text-[13px] font-medium">{p.name}</span></span><StatusBadge status={p.active ? "active" : "inactive"} /></button>)}</div>
        {form && <div className="space-y-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4"><h3 className="font-display font-semibold">{form.name || "New partner"} <span className="text-xs text-slate-400 font-normal ml-2">v{form.version || 1}</span></h3><button data-testid="partner-save-btn" onClick={save} className="h-9 px-4 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Save className="h-3.5 w-3.5" />Save</button></div>
            <div className="grid md:grid-cols-3 gap-4">
              {f("code", "Partner code")}{f("name", "Partner name")}{f("active", "Active", null, { bool: true, items: [{ v: true, l: "Active" }, { v: false, l: "Inactive" }] })}
              {f("partial_ingestion", "Partial ingestion", null, { bool: true, items: [{ v: true, l: "ON — valid rows load, bad rows → exceptions" }, { v: false, l: "OFF — any rejected row fails the file" }] })}
              {f("expected_frequency", "Expected submission", null, { items: ["daily", "weekly", "monthly", "none"].map((x) => ({ v: x, l: x })) })}{f("date_format_hint", "Date format hint")}
              {f("keywords", "Recognition keywords (filename / content)")}{f("store_code_prefix", "Store code prefix")}{f("contact_name", "Contact name")}
              {f("sender_domains", "Sender domains (email ingestion)")}{f("sender_emails", "Sender emails")}{f("subject_patterns", "Subject patterns")}
              <Field label="Expected columns (reference)" className="md:col-span-2"><input data-testid="partner-form-expected_columns" value={form.expected_columns} onChange={(e) => setForm({ ...form, expected_columns: e.target.value })} className={inputCls} /></Field>{f("contact_email", "Contact email")}
              <Field label="Notes" className="md:col-span-3"><input data-testid="partner-form-notes" value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} className={inputCls} /></Field>
            </div>
          </div>
          {stats && <div className="grid md:grid-cols-4 gap-3" data-testid="partner-stats">{[["Batches", stats.batches], ["Active stores", stats.stores], ["Learned aliases", stats.learned_aliases], ["Last file", stats.last_batch ? `${fmtDate(stats.last_batch.created_at)} · ${stats.last_batch.status}` : "—"]].map(([l, v]) => <div key={l} className="card p-3"><div className="label-caps">{l}</div><div className="font-display text-lg font-bold mt-1 truncate">{v}</div></div>)}</div>}
          <div className="card" data-testid="partner-mapping-versions"><div className="px-5 py-3 border-b font-display font-semibold">Approved mapping versions <span className="text-xs text-slate-400 font-normal">history is never overwritten</span></div>
            {mappings.length === 0 ? <div className="p-5 text-xs text-slate-400">No learned mappings yet — approve a mapping with "remember" enabled.</div> : <table className="data-table w-full"><thead><tr><th>Version</th><th>Status</th><th>Mapping</th><th>By</th><th>When</th></tr></thead><tbody>{mappings.map((m) => <tr key={m.id}><td className="font-mono">v{m.version}</td><td><StatusBadge status={m.active ? "active" : "inactive"} /></td><td><div className="flex flex-wrap gap-1 max-w-xl">{Object.entries(m.mapping).map(([h, fl]) => <span key={h} className="chip bg-slate-100 text-slate-600 font-normal">{h} → <b>{fl}</b></span>)}</div></td><td className="text-xs">{m.created_by}</td><td className="text-xs text-slate-500">{fmtDate(m.created_at)}</td></tr>)}</tbody></table>}
          </div>
        </div>}
      </div>
    </div>
  );
}
