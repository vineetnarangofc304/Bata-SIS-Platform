import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Download, Save, Trash2, Columns3 } from "lucide-react";
import api, { errMsg, downloadFile } from "@/lib/api";
import { inr, num, pct } from "@/lib/format";
import { DataTable, PageHeader, selectCls, inputCls } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const fmt = (v, t) => t === "money" ? inr(v, { decimals: 0 }) : t === "int" ? num(v) : t === "pct" ? pct(v) : t === "calendar" ? (v ? <span className="chip bg-emerald-50 text-emerald-700">{v}</span> : <span className="chip bg-red-50 text-red-600">—</span>) : (v ?? "—");
const REC_COLS = ["sale_date", "partner_name", "store_code", "store_name", "region", "sku", "article_name", "category", "quantity", "unit_price", "discount", "tax", "net_amount", "invoice_no", "data_quality"];

export default function Reports() {
  const [sp, setSp] = useSearchParams();
  const nav = useNavigate();
  const [list, setList] = useState([]);
  const [partners, setPartners] = useState([]);
  const [views, setViews] = useState([]);
  const report = sp.get("report") || "daily_sales";
  const [params, setParams] = useState(() => Object.fromEntries([...sp.entries()].filter(([k]) => k !== "report")));
  const [res, setRes] = useState(null);
  const [recs, setRecs] = useState(null);
  const [page, setPage] = useState(1);
  const [hidden, setHidden] = useState([]);
  const [sort, setSort] = useState({ by: "", dir: "desc" });
  const [loading, setLoading] = useState(false);
  useEffect(() => { api.get("/reports").then((r) => setList(r.data)); api.get("/partners").then((r) => setPartners(r.data)); loadViews(); }, []);
  const loadViews = () => api.get("/saved-views").then((r) => setViews(r.data));
  const q = { ...Object.fromEntries(Object.entries(params).filter(([, v]) => v)), ...(sort.by ? { sort_by: sort.by, sort_dir: sort.dir } : {}) };
  const run = useCallback(() => {
    setLoading(true);
    if (report === "records") api.get("/reports/records", { params: { ...q, page, page_size: 50 } }).then((r) => setRecs(r.data)).finally(() => setLoading(false));
    else api.get(`/reports/${report}`, { params: q }).then((r) => setRes(r.data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  }, [report, JSON.stringify(q), page]); // eslint-disable-line
  useEffect(() => { run(); }, [run]);
  const setReport = (r) => { const n = new URLSearchParams({ report: r }); setSp(n); setHidden([]); setSort({ by: "", dir: "desc" }); setPage(1); };
  const setP = (k, v) => { setParams((p) => ({ ...p, [k]: v })); setPage(1); };
  const drill = (row) => { const p = {}; ["partner_code", "store_code", "sku", "region", "category"].forEach((k) => { if (row[k]) p[k] = row[k]; }); if (row.sale_date) { p.date_from = row.sale_date; p.date_to = row.sale_date; } if (row.month) { p.date_from = `${row.month}-01`; p.date_to = `${row.month}-31`; } if (row.partner_name && !row.partner_code) { const pc = partners.find((x) => x.name === row.partner_name)?.code; if (pc) p.partner_code = pc; } setParams({ ...params, ...p }); setSp(new URLSearchParams({ report: "records" })); setPage(1); };
  const saveView = async () => { const name = window.prompt("Name this view"); if (!name) return; await api.post("/saved-views", { name, report, params, columns: hidden.length ? res?.columns.filter((c) => !hidden.includes(c.key)).map((c) => c.key) : null }); toast.success("View saved"); loadViews(); };
  const applyView = (v) => { setParams(v.params || {}); setSp(new URLSearchParams({ report: v.report })); if (v.columns && res) setHidden(res.columns.map((c) => c.key).filter((k) => !v.columns.includes(k))); };
  const exportIt = (f) => { const cols = res ? res.columns.filter((c) => !hidden.includes(c.key)).map((c) => c.key).join(",") : undefined; downloadFile(report === "records" ? "/reports/records/export" : `/reports/${report}/export`, `${report}.${f}`, { ...q, fmt: f, columns: cols }); };
  const visible = res?.columns.filter((c) => !hidden.includes(c.key)) || [];
  const cols = report === "records"
    ? [...REC_COLS.map((k) => ({ key: k, label: k.replace(/_/g, " "), render: (r) => k === "data_quality" ? <StatusBadge status={r[k]} /> : ["quantity"].includes(k) ? num(r[k]) : ["unit_price", "discount", "tax", "net_amount"].includes(k) ? inr(r[k], { decimals: 2 }) : <span className="whitespace-nowrap">{r[k] ?? "—"}</span> })), { key: "batch_id", label: "Batch", render: (r) => <button onClick={() => nav(`/batches/${r.batch_id}`)} className="text-[#E60000] font-mono text-xs hover:underline" data-testid="record-batch-link">{r.batch_id.slice(0, 8).toUpperCase()}</button> }]
    : visible.map((c) => ({ key: c.key, label: c.label, sortIndicator: sort.by === c.key ? (sort.dir === "desc" ? " ↓" : " ↑") : "", onSort: c.type !== "calendar" ? () => setSort((s) => ({ by: c.key, dir: s.by === c.key && s.dir === "desc" ? "asc" : "desc" })) : undefined, cellClass: ["money", "int", "pct"].includes(c.type) ? "text-right tabular" : "", className: ["money", "int", "pct"].includes(c.type) ? "text-right" : "", render: (r) => fmt(r[c.key], c.type) }));
  const footer = res?.totals && <tr className="bg-slate-50 font-semibold"><td colSpan={visible.filter((c) => !res.totals[c.key]).length || 1} className="text-xs uppercase text-slate-500">Total</td>{visible.filter((c) => res.totals[c.key] !== undefined).map((c) => <td key={c.key} className="text-right tabular">{fmt(res.totals[c.key], c.type)}</td>)}{visible.filter((c) => res.totals[c.key] === undefined).slice(1).map((c) => <td key={c.key} />)}</tr>;
  return (
    <div data-testid="reports-page">
      <PageHeader title="Sales Reports" sub="12 standard reports plus source-record drill-down. Every aggregate traces back to the batch and row it came from." actions={<>
        <button data-testid="reports-save-view-btn" onClick={saveView} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><Save className="h-3.5 w-3.5" />Save view</button>
        <button data-testid="reports-export-csv-btn" onClick={() => exportIt("csv")} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><Download className="h-3.5 w-3.5" />CSV</button>
        <button data-testid="reports-export-excel-btn" onClick={() => exportIt("xlsx")} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Download className="h-3.5 w-3.5" />Excel</button></>} />
      <div className="grid lg:grid-cols-[220px_1fr] gap-5">
        <div className="space-y-4">
          <div className="card p-2" data-testid="reports-list">{[...list, { key: "records", name: "Source Records (drill-down)" }].map((r) => <button key={r.key} data-testid={`report-${r.key}`} onClick={() => setReport(r.key)} className={`w-full text-left px-3 py-2 rounded text-[13px] ${report === r.key ? "bg-[#E60000] text-white font-semibold" : "text-slate-700 hover:bg-slate-100"}`}>{r.name}</button>)}</div>
          {views.length > 0 && <div className="card p-2"><div className="label-caps px-2 py-1">Saved views</div>{views.map((v) => <div key={v.id} className="flex items-center group"><button data-testid="saved-view-item" onClick={() => applyView(v)} className="flex-1 text-left px-3 py-1.5 rounded text-xs text-slate-700 hover:bg-slate-100 truncate">{v.name}<span className="text-slate-400"> · {v.report}</span></button><button onClick={() => api.delete(`/saved-views/${v.id}`).then(loadViews)} className="p-1 opacity-0 group-hover:opacity-100"><Trash2 className="h-3 w-3 text-slate-400" /></button></div>)}</div>}
        </div>
        <div>
          <div className="flex flex-wrap gap-2 mb-3 items-center">
            <input type="date" data-testid="reports-date-from" value={params.date_from || ""} onChange={(e) => setP("date_from", e.target.value)} className={inputCls} /><span className="text-slate-400 text-xs">to</span><input type="date" data-testid="reports-date-to" value={params.date_to || ""} onChange={(e) => setP("date_to", e.target.value)} className={inputCls} />
            <select data-testid="reports-filter-partner" value={params.partner_code || ""} onChange={(e) => setP("partner_code", e.target.value)} className={selectCls}><option value="">All partners</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select>
            <select data-testid="reports-filter-region" value={params.region || ""} onChange={(e) => setP("region", e.target.value)} className={selectCls}><option value="">All regions</option>{["North", "South", "East", "West"].map((r) => <option key={r}>{r}</option>)}</select>
            <input data-testid="reports-filter-category" value={params.category || ""} onChange={(e) => setP("category", e.target.value)} placeholder="Category" className={inputCls + " w-36"} />
            <input data-testid="reports-filter-store" value={params.store_code || ""} onChange={(e) => setP("store_code", e.target.value)} placeholder="Store code" className={inputCls + " w-28"} />
            <input data-testid="reports-filter-sku" value={params.sku || ""} onChange={(e) => setP("sku", e.target.value)} placeholder="Article" className={inputCls + " w-28"} />
            {report === "missing_submissions" && <select value={params.days || "14"} onChange={(e) => setP("days", e.target.value)} className={selectCls}>{[7, 14, 30].map((d) => <option key={d} value={d}>{d} days</option>)}</select>}
            {report === "top_bottom" && <select value={params.limit || "10"} onChange={(e) => setP("limit", e.target.value)} className={selectCls}>{[5, 10, 20].map((d) => <option key={d} value={d}>Top/Bottom {d}</option>)}</select>}
            {Object.values(params).some(Boolean) && <button data-testid="reports-clear-filters" onClick={() => setParams({})} className="text-xs text-[#E60000] hover:underline">Clear</button>}
            {res && <Popover><PopoverTrigger asChild><button data-testid="reports-columns-btn" className="ml-auto h-9 px-3 rounded-md border text-xs flex items-center gap-1 hover:bg-slate-50"><Columns3 className="h-3.5 w-3.5" />Columns</button></PopoverTrigger><PopoverContent align="end" className="w-56 p-2 text-xs max-h-72 overflow-auto">{res.columns.map((c) => <label key={c.key} className="flex items-center gap-2 px-2 py-1 hover:bg-slate-50 rounded cursor-pointer"><input type="checkbox" data-testid={`column-toggle-${c.key}`} checked={!hidden.includes(c.key)} onChange={(e) => setHidden((h) => e.target.checked ? h.filter((x) => x !== c.key) : [...h, c.key])} className="accent-[#E60000]" />{c.label}</label>)}</PopoverContent></Popover>}
          </div>
          {report === "records" ? <DataTable testId="records-table" dense columns={cols} rows={recs?.items} loading={loading && !recs} page={page} pages={recs?.pages} total={recs?.total} onPage={setPage} />
            : <><div className="text-xs text-slate-500 mb-2">{res?.name} · {res?.rows?.length ?? 0} rows · click a row to drill down to source records · click headers to sort</div>
              <DataTable testId="report-table" dense columns={cols} rows={res?.rows} loading={loading && !res} onRowClick={["data_quality_trend", "missing_submissions", "exception_summary"].includes(report) ? undefined : drill} footer={footer} /></>}
        </div>
      </div>
    </div>
  );
}
