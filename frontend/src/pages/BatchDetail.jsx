import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Download, RefreshCw, Ban, ArrowLeft, CheckCircle2 } from "lucide-react";
import api, { errMsg, downloadFile } from "@/lib/api";
import { fmtDate, shortId } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DataTable, selectCls } from "@/components/common/DataTable";
import { StatusBadge, Counts, ConfidenceBadge } from "@/components/common/Badges";
import { MappingReview } from "@/components/batch/MappingReview";

export default function BatchDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { isOps } = useAuth();
  const [b, setB] = useState(null);
  const [rows, setRows] = useState(null);
  const [rowStatus, setRowStatus] = useState("");
  const [layer, setLayer] = useState("standardized");
  const [page, setPage] = useState(1);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api.get(`/batches/${id}`).then((r) => setB(r.data)).catch((e) => toast.error(errMsg(e))), [id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (b && ["Received", "Analysing", "Validating"].includes(b.status)) { const t = setTimeout(load, 2000); return () => clearTimeout(t); } }, [b, load]);
  useEffect(() => { api.get(`/batches/${id}/rows`, { params: { page, page_size: 50, status: rowStatus || undefined, layer } }).then((r) => setRows(r.data)); }, [id, page, rowStatus, layer, b?.status, b?.counts?.accepted]);
  useEffect(() => { api.get("/audit-logs", { params: { batch_id: id, page_size: 100 } }).then((r) => setAudit(r.data.items)); }, [id, b?.status]);

  const act = async (path, ok) => { setBusy(true); try { await api.post(`/batches/${id}/${path}`, path === "reject" ? { reason: "Rejected by operator from batch view" } : {}); toast.success(ok); load(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } };
  if (!b) return <div className="text-slate-400 text-sm">Loading batch…</div>;
  const cb = b.confidence_breakdown;
  const fields = b.column_mappings?.filter((c) => c.proposed_field).map((c) => c.proposed_field) || [];
  return (
    <div data-testid="batch-detail-page">
      <button onClick={() => nav(-1)} className="text-xs text-slate-500 hover:text-slate-800 flex items-center gap-1 mb-3"><ArrowLeft className="h-3 w-3" />Back</button>
      <div className="card p-5 fade-up">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap"><h1 className="font-display text-xl font-bold text-slate-900 truncate" data-testid="batch-file-name">{b.file_name}</h1><StatusBadge status={b.status} testId="batch-detail-status" />{b.reprocessed && <span className="chip bg-indigo-50 text-indigo-700">reprocessed ×{b.reprocess_count || 1}</span>}</div>
            <div className="text-xs text-slate-500 mt-1 flex flex-wrap gap-x-4 gap-y-1"><span>Batch <span className="font-mono">{shortId(b.id)}</span></span><span>Partner: <b className="text-slate-700">{b.partner_name || "Unidentified"}</b></span><span>Source: {b.source}</span><span>By {b.uploaded_by}</span><span>{fmtDate(b.created_at)}</span><span>{(b.file_size / 1024).toFixed(0)} KB</span>{b.period && <span>Period {b.period.from} → {b.period.to}</span>}<span>Sheet: {b.selected_sheet || "—"} · header row {b.header_row !== undefined ? b.header_row + 1 : "—"}</span></div>
          </div>
          <div className="flex gap-2 flex-wrap">
            {b.storage_path && <button data-testid="batch-download-original" onClick={() => downloadFile(`/batches/${id}/download`, b.file_name)} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><Download className="h-3.5 w-3.5" />Original</button>}
            {isOps && b.column_mappings && !["Rejected", "Superseded", "Received", "Analysing", "Validating"].includes(b.status) && <button data-testid="batch-reprocess-btn" disabled={busy} onClick={() => act("reprocess", "Batch reprocessed")} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><RefreshCw className="h-3.5 w-3.5" />Reprocess</button>}
            {isOps && !["Rejected", "Superseded"].includes(b.status) && <button data-testid="batch-reject-btn" disabled={busy} onClick={() => window.confirm("Reject this entire file? Loaded rows will be removed from reporting.") && act("reject", "Batch rejected")} className="h-9 px-3 rounded-md border border-red-200 text-red-700 text-xs font-medium hover:bg-red-50 flex items-center gap-1"><Ban className="h-3.5 w-3.5" />Reject file</button>}
          </div>
        </div>
        {(b.review_reason || b.rejection_reason || b.failure_reason || b.row_count_anomaly) && (
          <div data-testid="batch-reason" className={`mt-4 rounded-md border px-4 py-3 text-sm ${b.status === "Awaiting Review" ? "bg-amber-50 border-amber-200 text-amber-900" : b.status === "Rejected" || b.status === "Failed" ? "bg-red-50 border-red-200 text-red-800" : "bg-blue-50 border-blue-200 text-blue-900"}`}>
            {b.review_reason || b.rejection_reason || b.failure_reason}{b.row_count_anomaly && <div className="text-xs mt-1 opacity-80">Anomaly: {b.row_count_anomaly}</div>}
            {b.duplicate_of && <button onClick={() => nav(`/batches/${b.duplicate_of}`)} className="ml-2 underline text-xs">Open original batch</button>}
            {b.restatement_of && b.status === "Awaiting Review" && isOps && <div className="mt-2 flex gap-2"><button data-testid="batch-approve-restatement-btn" disabled={busy} onClick={() => act("approve-restatement", "Restatement approved — prior batch superseded")} className="h-8 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />Approve & supersede prior batch</button><button onClick={() => nav(`/batches/${b.restatement_of}`)} className="h-8 px-3 rounded-md border text-xs">View prior batch</button></div>}
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-5">
          {[["Total rows", b.counts.total, ""], ["Accepted", b.counts.accepted, "text-emerald-600"], ["Warnings", b.counts.warning, "text-amber-600"], ["Rejected", b.counts.rejected, "text-red-600"], ["Duplicates", b.counts.duplicate, "text-slate-500"], ["Open exceptions", b.open_exceptions, "text-amber-600"]].map(([l, v, c]) => <div key={l} className="border rounded-md p-3" data-testid={`batch-count-${l.toLowerCase().replace(/ /g, "-")}`}><div className="label-caps">{l}</div><div className={`font-display text-2xl font-bold tabular ${c}`}>{v ?? 0}</div></div>)}
        </div>
        {cb && <div className="mt-4 flex flex-wrap gap-6 text-xs text-slate-600 items-center" data-testid="batch-confidence">
          <span className="flex items-center gap-2"><span className="label-caps">Overall</span><ConfidenceBadge value={cb.overall} level={cb.level} /></span>
          <span className="flex items-center gap-2"><span className="label-caps">Partner</span><ConfidenceBadge value={cb.partner} /></span>
          <span className="flex items-center gap-2"><span className="label-caps">Header row</span><ConfidenceBadge value={cb.header_row} /></span>
          <span className="flex items-center gap-2"><span className="label-caps">Columns</span><ConfidenceBadge value={cb.columns_avg} /><span className="text-slate-400">{cb.mapped_count}/{cb.total_columns} mapped</span></span>
          {b.mapping_approved_by && <span className="text-slate-500">Mapping approved by <b>{b.mapping_approved_by}</b>{b.mapping_version && ` · saved as v${b.mapping_version}`}</span>}
          {b.partner_detection && <span className="text-slate-400 italic">{b.partner_detection.reason}</span>}
        </div>}
      </div>
      <Tabs defaultValue={b.status === "Awaiting Review" ? "mapping" : "rows"} className="mt-5">
        <TabsList className="bg-white border">
          <TabsTrigger value="mapping" data-testid="tab-mapping">Column mapping</TabsTrigger><TabsTrigger value="rows" data-testid="tab-rows">Rows</TabsTrigger><TabsTrigger value="exceptions" data-testid="tab-exceptions">Exceptions ({b.open_exceptions || 0})</TabsTrigger><TabsTrigger value="preview" data-testid="tab-preview">Source preview</TabsTrigger><TabsTrigger value="timeline" data-testid="tab-timeline">Timeline & audit</TabsTrigger>
        </TabsList>
        <TabsContent value="mapping" className="mt-4">{b.column_mappings ? <MappingReview batch={b} onDone={load} /> : <div className="card p-8 text-center text-sm text-slate-400">Analysis pending…</div>}</TabsContent>
        <TabsContent value="rows" className="mt-4">
          <div className="flex gap-2 mb-3">
            <select data-testid="rows-layer-select" value={layer} onChange={(e) => { setLayer(e.target.value); setPage(1); }} className={selectCls}><option value="standardized">Standardized rows (current version)</option><option value="raw">Raw extracted rows</option><option value="reporting">Reporting rows (loaded)</option></select>
            {layer === "standardized" && <select data-testid="rows-status-filter" value={rowStatus} onChange={(e) => { setRowStatus(e.target.value); setPage(1); }} className={selectCls}><option value="">All statuses</option><option value="accepted">Accepted</option><option value="warning">Warning</option><option value="rejected">Rejected</option><option value="duplicate">Duplicate</option></select>}
          </div>
          {layer === "raw" && <DataTable testId="raw-rows" dense columns={[{ key: "row_index", label: "#" }, { key: "source_row", label: "Src row" }, ...(b.headers || []).map((h) => ({ key: h, label: h, render: (r) => <span className="whitespace-nowrap">{String(r.data?.[h] ?? "")}</span> }))]} rows={rows?.items} loading={!rows} page={page} pages={rows?.pages} total={rows?.total} onPage={setPage} />}
          {layer === "reporting" && <DataTable testId="reporting-rows" dense columns={["sale_date", "store_code", "store_name", "sku", "article_name", "category", "quantity", "unit_price", "discount", "tax", "net_amount", "invoice_no", "data_quality"].map((k) => ({ key: k, label: k.replace(/_/g, " "), render: (r) => k === "data_quality" ? <StatusBadge status={r[k]} /> : <span className="whitespace-nowrap">{r[k] ?? "—"}</span> }))} rows={rows?.items} loading={!rows} page={page} pages={rows?.pages} total={rows?.total} onPage={setPage} />}
          {layer === "standardized" && <DataTable testId="std-rows" dense columns={[
            { key: "row_index", label: "#", render: (r) => <span className="font-mono text-slate-400">{r.row_index}<span className="text-[10px]"> v{r.version}</span></span> },
            { key: "status", label: "Status", render: (r) => <StatusBadge status={r.status} /> },
            ...fields.map((f) => ({ key: f, label: f.replace(/_/g, " "), render: (r) => { const v = r.values?.[f]; const o = r.original_values?.[f]; const changed = o !== null && o !== undefined && String(v) !== String(o); return <span className="whitespace-nowrap" title={changed ? `Original: ${o}` : ""}>{v ?? <span className="text-red-400">∅</span>}{changed && <span className="text-[10px] text-slate-400 ml-1 line-through">{o}</span>}</span>; } })),
            { key: "issues", label: "Issues", render: (r) => r.issues?.length ? <div className="flex flex-wrap gap-1">{r.issues.map((i, k) => <span key={k} className="chip bg-red-50 text-red-700" title={i.message}>{i.rule_code}</span>)}</div> : <span className="text-emerald-600 text-xs">✓</span> },
          ]} rows={rows?.items} loading={!rows} page={page} pages={rows?.pages} total={rows?.total} onPage={setPage} />}
        </TabsContent>
        <TabsContent value="exceptions" className="mt-4"><div className="card p-6 text-sm">This batch has <b>{b.open_exceptions || 0}</b> open exception(s). <button data-testid="open-exceptions-workbench" onClick={() => nav(`/review?batch=${id}`)} className="text-[#E60000] font-semibold hover:underline">Open in the exception workbench →</button></div></TabsContent>
        <TabsContent value="preview" className="mt-4"><div className="card overflow-auto max-h-[480px]"><table className="text-xs w-full"><tbody>{(b.preview_rows || []).map((row, ri) => <tr key={ri} className={ri === b.header_row ? "bg-red-50 font-semibold" : ri < b.header_row ? "text-slate-400 italic" : ""}><td className="px-2 py-1 border-b border-r bg-slate-50 text-slate-400 font-mono w-8">{ri + 1}</td>{row.map((c, ci) => <td key={ci} className="px-2 py-1 border-b border-slate-100 whitespace-nowrap max-w-[180px] truncate">{c ?? ""}</td>)}</tr>)}</tbody></table>{b.sheets?.length > 1 && <div className="px-4 py-2 text-xs text-slate-500 border-t">Sheets: {b.sheets.map((s) => `${s.name} (${s.data_rows} rows, ${s.mapped_columns} mapped cols)`).join(" · ")} — selected <b>{b.selected_sheet}</b></div>}</div></TabsContent>
        <TabsContent value="timeline" className="mt-4">
          <div className="grid lg:grid-cols-2 gap-4">
            <div className="card p-5"><h3 className="font-display font-semibold mb-3">Status timeline</h3><ol className="space-y-3">{b.status_history?.map((h, i) => <li key={i} className="flex gap-3 text-sm" data-testid="timeline-item"><span className="mt-1 h-2 w-2 rounded-full bg-[#E60000] shrink-0" /><div><StatusBadge status={h.status} /> <span className="text-xs text-slate-500 ml-2">{fmtDate(h.at)} · {h.by}</span>{h.reason && <div className="text-xs text-slate-600 mt-0.5">{h.reason}</div>}</div></li>)}</ol></div>
            <div className="card p-5"><h3 className="font-display font-semibold mb-3">Audit trail</h3><div className="space-y-2 max-h-96 overflow-auto">{audit.map((a) => <div key={a.id} className="text-xs border-b border-slate-100 pb-2" data-testid="audit-item"><span className="font-mono text-[#E60000]">{a.action}</span> <span className="text-slate-500">by {a.actor} · {fmtDate(a.created_at)}</span>{a.details && Object.keys(a.details).length > 0 && <pre className="text-[10px] text-slate-500 mt-1 whitespace-pre-wrap font-mono">{JSON.stringify(a.details).slice(0, 300)}</pre>}</div>)}</div></div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
