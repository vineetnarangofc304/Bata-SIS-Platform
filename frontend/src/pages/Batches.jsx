import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Inbox, CheckCircle2, XCircle, AlertTriangle, Download } from "lucide-react";
import api, { downloadFile } from "@/lib/api";
import { fmtDate, shortId, num } from "@/lib/format";
import { DataTable, PageHeader, KpiCard, selectCls, inputCls } from "@/components/common/DataTable";
import { StatusBadge, Counts, ConfidenceBadge } from "@/components/common/Badges";

const STATUSES = ["Received", "Analysing", "Awaiting Review", "Validating", "Partially Processed", "Successfully Processed", "Failed", "Rejected", "Superseded"];

export default function Batches() {
  const [sp, setSp] = useSearchParams();
  const [data, setData] = useState(null);
  const [summary, setSummary] = useState(null);
  const [partners, setPartners] = useState([]);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const nav = useNavigate();
  const status = sp.get("status") || "", partner = sp.get("partner_code") || "";
  const set = (k, v) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n); setPage(1); };
  useEffect(() => { api.get("/partners").then((r) => setPartners(r.data)); }, []);
  useEffect(() => {
    const load = () => { api.get("/batches", { params: { page, page_size: 25, status: status || undefined, partner_code: partner || undefined, search: search || undefined } }).then((r) => setData(r.data)); api.get("/batches/summary").then((r) => setSummary(r.data)); };
    load(); const t = setInterval(load, 8000); return () => clearInterval(t);
  }, [page, status, partner, search]);
  const s = summary?.by_status || {};
  const sum = (keys, f) => keys.reduce((a, k) => a + (s[k]?.[f] || 0), 0);
  const cols = [
    { key: "id", label: "Batch", render: (b) => <span className="font-mono text-xs text-slate-500">{shortId(b.id)}</span> },
    { key: "file_name", label: "File", render: (b) => <div className="max-w-[260px]"><div className="font-medium text-slate-800 truncate" title={b.file_name}>{b.file_name}</div><div className="text-[11px] text-slate-400">{b.source} · {b.uploaded_by} · {(b.file_size / 1024).toFixed(0)} KB</div></div> },
    { key: "partner_name", label: "Partner", render: (b) => b.partner_name || <span className="text-amber-600 text-xs">Unidentified</span> },
    { key: "status", label: "Status", render: (b) => <div><StatusBadge status={b.status} testId="batch-status" />{b.reprocessed && <span className="chip bg-indigo-50 text-indigo-700 ml-1">reprocessed</span>}</div> },
    { key: "counts", label: "Rows (T · A · W · R · D)", render: (b) => <Counts counts={b.counts} /> },
    { key: "confidence", label: "Confidence", render: (b) => <ConfidenceBadge value={b.confidence} level={b.confidence_level} /> },
    { key: "period", label: "Period", render: (b) => b.period ? <span className="text-xs tabular">{b.period.from} → {b.period.to}</span> : "—" },
    { key: "created_at", label: "Received", render: (b) => <span className="text-xs text-slate-500">{fmtDate(b.created_at)}</span> },
    { key: "actions", label: "", render: (b) => <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
      {b.status === "Awaiting Review" && <button data-testid="batch-action-review-btn" onClick={() => nav(`/batches/${b.id}`)} className="chip bg-amber-500 text-white hover:bg-amber-600">Review</button>}
      {b.storage_path && <button data-testid="batch-download-btn" title="Download original" onClick={() => downloadFile(`/batches/${b.id}/download`, b.file_name)} className="p-1 rounded hover:bg-slate-100"><Download className="h-3.5 w-3.5 text-slate-500" /></button>}
    </div> },
  ];
  return (
    <div data-testid="batches-page">
      <PageHeader title="Ingestion Batches" sub="Every upload or email becomes a batch. What arrived, what was accepted, what failed, what needs action." />
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger" data-testid="ingestion-hero-banner">
        <KpiCard testId="hero-received" label="Files received" value={num(summary?.total_batches)} icon={Inbox} sub={`${summary?.processing || 0} processing now`} />
        <KpiCard testId="hero-accepted" label="Rows accepted" value={num(sum(["Successfully Processed", "Partially Processed"], "accepted") + sum(["Successfully Processed", "Partially Processed"], "warning"))} icon={CheckCircle2} tone="green" sub={`${s["Successfully Processed"]?.n || 0} clean · ${s["Partially Processed"]?.n || 0} partial batches`} />
        <KpiCard testId="hero-failed" label="Rows rejected" value={num(sum(STATUSES, "rejected"))} icon={XCircle} tone="red" sub={`${(s.Failed?.n || 0) + (s.Rejected?.n || 0)} batches failed/rejected · ${sum(STATUSES, "duplicate")} duplicate rows`} />
        <KpiCard testId="hero-action" label="Needs action" value={num((summary?.awaiting_review || 0) + (summary?.open_exceptions || 0))} icon={AlertTriangle} tone="amber" sub={`${summary?.awaiting_review || 0} batches awaiting review · ${summary?.open_exceptions || 0} open exceptions`} onClick={() => set("status", "Awaiting Review")} />
      </div>
      <div className="flex flex-wrap gap-2 mt-6 mb-3">
        <input data-testid="batches-search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search file or batch id…" className={inputCls + " w-64"} />
        <select data-testid="batches-status-filter" value={status} onChange={(e) => set("status", e.target.value)} className={selectCls}><option value="">All statuses</option>{STATUSES.map((x) => <option key={x}>{x}</option>)}</select>
        <select data-testid="batches-partner-filter" value={partner} onChange={(e) => set("partner_code", e.target.value)} className={selectCls}><option value="">All partners</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select>
      </div>
      <DataTable testId="ingestion-batch" columns={cols} rows={data?.items} loading={!data} page={page} pages={data?.pages} total={data?.total} onPage={setPage} onRowClick={(b) => nav(`/batches/${b.id}`)} />
    </div>
  );
}
