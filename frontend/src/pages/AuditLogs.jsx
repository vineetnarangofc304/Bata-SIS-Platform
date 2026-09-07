import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import { fmtDate, shortId } from "@/lib/format";
import { DataTable, PageHeader, inputCls, selectCls } from "@/components/common/DataTable";

export default function AuditLogs() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [f, setF] = useState({ category: "", actor: "", search: "", date_from: "", date_to: "" });
  const [open, setOpen] = useState(null);
  const nav = useNavigate();
  useEffect(() => { api.get("/audit-logs", { params: { page, page_size: 50, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) } }).then((r) => setData(r.data)); }, [page, f]);
  const set = (k, v) => { setF((x) => ({ ...x, [k]: v })); setPage(1); };
  return (
    <div data-testid="audit-page">
      <PageHeader title="Audit Logs" sub="Append-only record of uploads, system decisions, mapping changes, corrections, approvals, rejections, reprocessing, configuration and user activity." />
      <div className="flex flex-wrap gap-2 mb-3">
        <input data-testid="audit-search" value={f.search} onChange={(e) => set("search", e.target.value)} placeholder="Search action / actor / entity…" className={inputCls + " w-64"} />
        <select data-testid="audit-category-filter" value={f.category} onChange={(e) => set("category", e.target.value)} className={selectCls}><option value="">All categories</option>{(data?.categories || []).map((c) => <option key={c}>{c}</option>)}</select>
        <input data-testid="audit-actor-filter" value={f.actor} onChange={(e) => set("actor", e.target.value)} placeholder="Actor" className={inputCls + " w-32"} />
        <input type="date" value={f.date_from} onChange={(e) => set("date_from", e.target.value)} className={inputCls} /><input type="date" value={f.date_to} onChange={(e) => set("date_to", e.target.value)} className={inputCls} />
      </div>
      <DataTable testId="audit-table" dense columns={[
        { key: "created_at", label: "When", render: (a) => <span className="text-xs text-slate-500 whitespace-nowrap">{fmtDate(a.created_at)}</span> },
        { key: "actor", label: "Actor", render: (a) => <span className="font-medium">{a.actor}</span> },
        { key: "action", label: "Action", render: (a) => <span className="font-mono text-xs text-[#E60000]">{a.action}</span> },
        { key: "category", label: "Category" },
        { key: "entity", label: "Entity", render: (a) => <span className="text-xs">{a.entity_type} {a.entity_id && <span className="font-mono text-slate-400">{shortId(a.entity_id)}</span>}</span> },
        { key: "batch_id", label: "Batch", render: (a) => a.batch_id ? <button onClick={(e) => { e.stopPropagation(); nav(`/batches/${a.batch_id}`); }} className="font-mono text-xs underline text-slate-600">{shortId(a.batch_id)}</button> : "—" },
        { key: "details", label: "Details", render: (a) => <span className="text-[11px] text-slate-500 font-mono truncate block max-w-md">{JSON.stringify(a.details)}</span> },
      ]} rows={data?.items} loading={!data} page={page} pages={data?.pages} total={data?.total} onPage={setPage} onRowClick={(a) => setOpen(a)} />
      {open && <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/30" onClick={() => setOpen(null)}><div className="card p-5 max-w-2xl w-full max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()} data-testid="audit-detail"><div className="font-mono text-[#E60000] font-semibold">{open.action}</div><div className="text-xs text-slate-500 mb-3">{open.actor} · {fmtDate(open.created_at)} · {open.category}</div><pre className="text-xs bg-slate-50 border rounded p-3 whitespace-pre-wrap font-mono">{JSON.stringify(open.details, null, 2)}</pre></div></div>}
    </div>
  );
}
