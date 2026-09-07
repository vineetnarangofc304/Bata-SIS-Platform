import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import api, { errMsg } from "@/lib/api";
import { fmtDate, shortId } from "@/lib/format";
import { DataTable, PageHeader, selectCls, inputCls } from "@/components/common/DataTable";
import { StatusBadge, ConfidenceBadge } from "@/components/common/Badges";
import { ExceptionDrawer } from "@/components/review/ExceptionDrawer";

export default function ReviewQueue() {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [queue, setQueue] = useState(null);
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [f, setF] = useState({ status: "open", batch_id: sp.get("batch") || "", partner_code: sp.get("partner_code") || "", rule_code: "", severity: "", search: "" });
  const [sel, setSel] = useState([]);
  const [openId, setOpenId] = useState(sp.get("exception") || null);
  const [users, setUsers] = useState([]);
  const load = useCallback(() => {
    api.get("/review-queue").then((r) => setQueue(r.data));
    api.get("/exceptions", { params: { page, page_size: 25, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) } }).then((r) => setData(r.data));
  }, [page, f]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/users").then((r) => setUsers(r.data.items)).catch(() => setUsers([])); }, []);
  const set = (k, v) => { setF((x) => ({ ...x, [k]: v })); setPage(1); setSel([]); };
  const bulk = async (action) => {
    let assignee; if (action === "assign") { assignee = window.prompt("Assign to username:"); if (!assignee) return; }
    try { const { data: r } = await api.post("/exceptions/bulk", { ids: sel, action, assignee, comment: "Bulk action from workbench" }); toast.success(`${r.done} exception(s) updated${r.errors.length ? `, ${r.errors.length} failed` : ""}`); setSel([]); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const facet = (k) => data?.facets?.[k] || [];
  const cols = [
    { key: "sel", label: <input type="checkbox" data-testid="exception-select-all" checked={data?.items?.length > 0 && sel.length === data.items.length} onChange={(e) => setSel(e.target.checked ? data.items.map((x) => x.id) : [])} />, render: (r) => <input type="checkbox" data-testid="exception-select" checked={sel.includes(r.id)} onClick={(e) => e.stopPropagation()} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id))} /> },
    { key: "severity", label: "Severity", render: (r) => <StatusBadge status={r.severity} /> },
    { key: "rule_code", label: "Rule", render: (r) => <span className="font-mono text-xs font-semibold text-slate-800">{r.rule_code}</span> },
    { key: "message", label: "Issue", render: (r) => <div className="max-w-md"><div className="text-slate-800">{r.message}</div>{r.proposed_value !== null && r.proposed_value !== undefined && <div className="text-[11px] text-emerald-700 mt-0.5">Proposed: <b className="font-mono">{String(r.proposed_value)}</b></div>}</div> },
    { key: "file_name", label: "Source", render: (r) => <div className="text-xs"><div className="text-slate-700 truncate max-w-[200px]" title={r.file_name}>{r.file_name}</div><div className="text-slate-400">{r.partner_name} · row {r.source_row || r.row_index} · <span className="font-mono">{shortId(r.batch_id)}</span></div></div> },
    { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
    { key: "assigned_to", label: "Assignee", render: (r) => r.assigned_to || <span className="text-slate-300">—</span> },
    { key: "created_at", label: "Raised", render: (r) => <span className="text-xs text-slate-500">{fmtDate(r.created_at)}</span> },
  ];
  return (
    <div data-testid="review-queue-page">
      <PageHeader title="Review Queue" sub="Mappings awaiting approval and the exception workbench. Corrections create new auditable row versions — nothing is overwritten." />
      {queue && queue.batches.length > 0 && (
        <div className="mb-6" data-testid="review-batches">
          <div className="label-caps mb-2">Batches awaiting review ({queue.batches.length})</div>
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3 stagger">
            {queue.batches.map((b) => (
              <button key={b.id} data-testid="review-batch-card" onClick={() => nav(`/batches/${b.id}`)} className="card card-hover p-4 text-left border-l-4 border-l-amber-400">
                <div className="flex items-center justify-between gap-2"><span className="font-medium text-slate-800 truncate">{b.file_name}</span><ConfidenceBadge value={b.confidence} level={b.confidence_level} /></div>
                <div className="text-xs text-slate-500 mt-1">{b.partner_name || "Partner unidentified"} · {b.counts?.total} rows · {fmtDate(b.created_at)}</div>
                <div className="text-xs text-amber-800 mt-2 line-clamp-2">{b.review_reason}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="flex items-center justify-between mb-2"><div className="label-caps">Exception workbench · {data?.total ?? "…"} matching {queue && <span className="text-slate-400 normal-case font-normal">· {queue.open_exceptions} open in total · {queue.assigned_to_me} assigned to you</span>}</div></div>
      <div className="flex flex-wrap gap-2 mb-3">
        <input data-testid="exception-search" value={f.search} onChange={(e) => set("search", e.target.value)} placeholder="Search message / value / file…" className={inputCls + " w-60"} />
        <select data-testid="exception-filter-status" value={f.status} onChange={(e) => set("status", e.target.value)} className={selectCls}><option value="open">Open</option><option value="all">All</option>{["accepted", "corrected", "resolved", "ignored", "rejected"].map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <select data-testid="exception-filter-type" value={f.rule_code} onChange={(e) => set("rule_code", e.target.value)} className={selectCls}><option value="">All rules</option>{facet("rule_code").map((x) => <option key={x.value} value={x.value}>{x.value} ({x.count})</option>)}</select>
        <select data-testid="exception-filter-severity" value={f.severity} onChange={(e) => set("severity", e.target.value)} className={selectCls}><option value="">All severities</option>{facet("severity").map((x) => <option key={x.value} value={x.value}>{x.value} ({x.count})</option>)}</select>
        <select data-testid="exception-filter-partner" value={f.partner_code} onChange={(e) => set("partner_code", e.target.value)} className={selectCls}><option value="">All partners</option>{facet("partner_code").map((x) => <option key={x.value} value={x.value}>{x.value} ({x.count})</option>)}</select>
        {f.batch_id && <button data-testid="exception-clear-batch" onClick={() => set("batch_id", "")} className="chip bg-slate-900 text-white h-9 px-3">Batch {shortId(f.batch_id)} ✕</button>}
        {sel.length > 0 && <div className="ml-auto flex gap-1 items-center text-xs" data-testid="exception-bulk-toolbar"><span className="text-slate-500 mr-1">{sel.length} selected</span>
          <button data-testid="exception-bulk-ignore-btn" onClick={() => bulk("ignore")} className="h-9 px-3 rounded-md border hover:bg-slate-50">Ignore</button><button data-testid="exception-bulk-reject-btn" onClick={() => bulk("reject_row")} className="h-9 px-3 rounded-md border border-red-200 text-red-700 hover:bg-red-50">Reject rows</button><button data-testid="exception-bulk-assign-btn" onClick={() => bulk("assign")} className="h-9 px-3 rounded-md border hover:bg-slate-50">Assign</button><button data-testid="exception-bulk-revalidate-btn" onClick={() => bulk("revalidate")} className="h-9 px-3 rounded-md border hover:bg-slate-50">Revalidate</button></div>}
      </div>
      <DataTable testId="exception" columns={cols} rows={data?.items} loading={!data} page={page} pages={data?.pages} total={data?.total} onPage={setPage} onRowClick={(r) => setOpenId(r.id)} emptyText="No exceptions match — the queue is clear." />
      {openId && <ExceptionDrawer id={openId} users={users} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}
