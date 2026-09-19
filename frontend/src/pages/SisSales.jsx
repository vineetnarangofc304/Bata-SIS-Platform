import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Download, Columns3, RotateCcw, Layers3 } from "lucide-react";
import api, { errMsg, downloadFile } from "@/lib/api";
import { PageHeader, selectCls, inputCls } from "@/components/common/DataTable";
import { HelpLink } from "@/components/common/HelpLink";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MultiSelect } from "@/components/sis/MultiSelect";
import { HeroBar } from "@/components/sis/HeroBar";
import { SisTable } from "@/components/sis/SisTable";

const SLICERS = [["partner", "Partner"], ["cluster_manager", "Cluster Mgr"], ["market", "Market"], ["state", "State"], ["city", "City"], ["store_name", "Store"], ["grpcat", "GRPCAT"], ["cat_name", "Category"], ["month", "Month"], ["week", "Week"], ["ltl", "LTL"], ["top_stores", "Top Stores"], ["existing_vs_new", "Exist/New"]];
const DEFAULT_HIER = ["cluster_manager", "", "", "", ""];

export default function SisSales() {
  const [sp, setSp] = useSearchParams();
  const [meta, setMeta] = useState(null);
  const [opts, setOpts] = useState({});
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [colMode, setColMode] = useState(sp.get("cols") || "sales");
  const [hidden, setHidden] = useState([]);
  const get = (k) => sp.get(k) || "";
  const list = (k) => (get(k) ? get(k).split(",") : []);
  const hier = useMemo(() => { const h = list("group_by"); return DEFAULT_HIER.map((d, i) => h[i] ?? (i === 0 ? d : "")); }, [sp]); // eslint-disable-line
  const page = Number(get("page") || 1);
  const sort = { by: get("sort_by"), dir: get("sort_dir") || "desc" };

  const update = (patch, resetPage = true) => {
    const n = new URLSearchParams(sp);
    Object.entries(patch).forEach(([k, v]) => { if (v === "" || v === null || v === undefined || (Array.isArray(v) && !v.length)) n.delete(k); else n.set(k, Array.isArray(v) ? v.join(",") : v); });
    if (resetPage) n.delete("page");
    setSp(n);
  };
  const filterParams = useMemo(() => { const o = {}; [...SLICERS.map((s) => s[0]), "till_date", "latest_wk", "latest_month", "search"].forEach((k) => { if (get(k)) o[k] = get(k); }); return o; }, [sp]); // eslint-disable-line

  useEffect(() => { api.get("/sis/meta").then((r) => setMeta(r.data)); }, []);
  useEffect(() => { api.get("/sis/filters", { params: filterParams }).then((r) => setOpts(r.data)); }, [JSON.stringify(filterParams)]); // eslint-disable-line
  const run = useCallback(() => {
    setLoading(true);
    const group_by = hier.filter(Boolean).join(",") || "cluster_manager";
    api.get("/sis/sales-report", { params: { ...filterParams, group_by, sort_by: sort.by || undefined, sort_dir: sort.by ? sort.dir : undefined, page, page_size: 50 } })
      .then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e))).finally(() => setLoading(false));
  }, [JSON.stringify(filterParams), hier.join(), sort.by, sort.dir, page]); // eslint-disable-line
  useEffect(() => { run(); }, [run]);

  const setHier = (i, v) => { const h = [...hier]; h[i] = v; update({ group_by: h.map((x) => x || "").join(",").replace(/,+$/, "") }); };
  const onSort = (k) => update({ sort_by: k, sort_dir: sort.by === k && sort.dir === "desc" ? "asc" : "desc" });
  const toggle = (k) => update({ [k]: get(k) ? "" : "1" });
  const drill = (row) => {
    const first = hier.find(Boolean);
    if (!first || row[first] === null || row[first] === undefined) return;
    const rest = hier.filter(Boolean).slice(1);
    const next = rest.length ? rest : [first === "partner" ? "store_name" : first === "cluster_manager" ? "partner" : first === "store_name" ? "grpcat" : "store_name"];
    const patch = { group_by: next.join(",") };
    if (SLICERS.some((s) => s[0] === first)) patch[first] = String(row[first]);
    else if (first === "store_code") patch.search = String(row[first]);
    update(patch);
  };
  const allCols = data?.columns || meta?.measures || [];
  const visible = allCols.filter((c) => (colMode === "all" || c.group === colMode) && !hidden.includes(c.key)).map((c) => c.key);
  const exportIt = (fmt) => downloadFile("/sis/sales-report/export", `sis_sales_report.${fmt}`, { ...filterParams, group_by: hier.filter(Boolean).join(",") || "cluster_manager", sort_by: sort.by || undefined, sort_dir: sort.dir, fmt, columns: visible.join(",") });
  const activeFilters = Object.keys(filterParams).length;

  return (
    <div data-testid="sis-sales-page">
      <PageHeader title={<span className="flex items-center gap-2">SIS Secondary Sales<HelpLink id="sis-report" title="How this report works" /></span>} sub="Secondary sales vs last year, targets, LTL growth and store productivity — Power BI-style sales matrix computed live on the ingested data." actions={<>
        <button data-testid="sis-reset" onClick={() => setSp(new URLSearchParams())} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><RotateCcw className="h-3.5 w-3.5" />Reset</button>
        <button data-testid="sis-export-csv" onClick={() => exportIt("csv")} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><Download className="h-3.5 w-3.5" />CSV</button>
        <button data-testid="sis-export-xlsx" onClick={() => exportIt("xlsx")} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Download className="h-3.5 w-3.5" />Excel</button></>} />

      <HeroBar t={data?.total} meta={data?.meta} />

      <div className="card p-3 mt-4 space-y-3" data-testid="sis-filter-bar">
        <div className="flex flex-wrap items-center gap-2">
          <span className="label-caps flex items-center gap-1 mr-1"><Layers3 className="h-3.5 w-3.5" />Hierarchy</span>
          {hier.map((h, i) => (
            <select key={i} data-testid={`sis-hier-${i + 1}`} value={h} onChange={(e) => setHier(i, e.target.value)} className={selectCls + " h-8 text-xs " + (h ? "border-[#E60000]" : "")}>
              <option value="">{i === 0 ? "Level 1" : `Level ${i + 1} · none`}</option>
              {meta?.hierarchy.map((o) => <option key={o.key} value={o.key} disabled={hier.includes(o.key) && h !== o.key}>{o.label}</option>)}
            </select>
          ))}
          <div className="ml-auto flex items-center gap-1">
            {[["till_date", "Till date"], ["latest_month", `Latest month${meta?.latest_month ? ` · ${meta.latest_month}` : ""}`], ["latest_wk", `Latest wk${meta?.latest_week ? ` · ${meta.latest_week}` : ""}`]].map(([k, l]) => (
              <button key={k} data-testid={`sis-toggle-${k}`} onClick={() => k === "till_date" ? update({ till_date: get("till_date") ? "" : "Yes" }) : toggle(k)} className={`chip px-2.5 py-1.5 border ${get(k) ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 hover:bg-slate-50"}`}>{l}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {SLICERS.map(([k, l]) => <MultiSelect key={k} testId={`sis-filter-${k}`} label={l} options={opts[k] || []} value={list(k)} onChange={(v) => update({ [k]: v })} width={k === "store_name" ? "w-52" : "w-36"} />)}
          <input data-testid="sis-search" value={get("search")} onChange={(e) => update({ search: e.target.value })} placeholder="Search store / article / city" className={inputCls + " h-9 w-52 text-xs"} />
          {activeFilters > 0 && <button data-testid="sis-clear-filters" onClick={() => update(Object.fromEntries(Object.keys(filterParams).map((k) => [k, ""])))} className="text-xs text-[#E60000] hover:underline">Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""}</button>}
          <div className="ml-auto flex items-center gap-1">
            {[["sales", "Sales"], ["finance", "Finance"], ["all", "All"]].map(([k, l]) => <button key={k} data-testid={`sis-cols-${k}`} onClick={() => { setColMode(k); update({ cols: k }, false); }} className={`chip px-2.5 py-1.5 border ${colMode === k ? "bg-[#E60000] text-white border-[#E60000]" : "bg-white text-slate-600"}`}>{l}</button>)}
            <Popover><PopoverTrigger asChild><button data-testid="sis-columns-btn" className="h-8 px-2.5 rounded-md border text-xs flex items-center gap-1 hover:bg-slate-50"><Columns3 className="h-3.5 w-3.5" />Columns</button></PopoverTrigger>
              <PopoverContent align="end" className="w-60 p-2 text-xs max-h-80 overflow-auto">{allCols.map((c) => <label key={c.key} className="flex items-center gap-2 px-2 py-1 hover:bg-slate-50 rounded cursor-pointer"><input type="checkbox" data-testid={`sis-col-${c.key}`} checked={!hidden.includes(c.key) && (colMode === "all" || c.group === colMode)} onChange={(e) => { if (colMode !== "all" && c.group !== colMode) setColMode("all"); setHidden((h) => e.target.checked ? h.filter((x) => x !== c.key) : [...h, c.key]); }} className="accent-[#E60000]" />{c.label}<span className="ml-auto text-slate-400">{c.group}</span></label>)}</PopoverContent></Popover>
          </div>
        </div>
      </div>

      <div className="text-xs text-slate-500 my-2">Click a column header to sort · use the ↳ icon on a row to drill into it · growth columns are coloured green/red · totals recomputed for the current filters (store counts are distinct, not summed)</div>
      <SisTable data={data} loading={loading && !data} visible={visible} sort={sort} onSort={onSort} page={page} onPage={(p) => update({ page: String(p) }, false)} onDrill={drill} />
    </div>
  );
}
