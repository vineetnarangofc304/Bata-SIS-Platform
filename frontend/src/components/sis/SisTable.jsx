import { ChevronLeft, ChevronRight, Loader2, ArrowDown, ArrowUp, CornerDownRight } from "lucide-react";
import { fmtCell, growthCls } from "./HeroBar";
import { HelpLink } from "@/components/common/HelpLink";

const RIGHT = ["money", "int", "num1", "pct", "growth"];

export function SisTable({ data, loading, visible, sort, onSort, page, onPage, onDrill }) {
  const dims = data?.dims || [];
  const cols = (data?.columns || []).filter((c) => visible.includes(c.key));
  const Th = ({ k, label, type, helpId }) => (
    <th onClick={() => onSort(k)} className={`cursor-pointer select-none ${RIGHT.includes(type) ? "text-right" : ""}`} data-testid={`sis-th-${k}`}>
      <span className="inline-flex items-center gap-1">{label}{helpId && <HelpLink id={helpId} />}{sort.by === k && (sort.dir === "desc" ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}</span>
    </th>
  );
  return (
    <div className="card overflow-hidden" data-testid="sis-table">
      <div className="overflow-x-auto max-h-[62vh]">
        <table className="data-table w-full text-xs">
          <thead className="sticky top-0 z-10"><tr>{dims.map((d) => <Th key={d.key} k={d.key} label={d.label} type="string" />)}{cols.map((c) => <Th key={c.key} k={c.key} label={c.label} type={c.type} helpId={`s-${c.key}`} />)}{onDrill && <th />}</tr></thead>
          <tbody>
            {loading && <tr><td colSpan={dims.length + cols.length + 1} className="py-10 text-center text-slate-400"><Loader2 className="inline h-4 w-4 animate-spin mr-2" />Computing…</td></tr>}
            {!loading && data?.rows?.length === 0 && <tr><td colSpan={dims.length + cols.length + 1} className="py-10 text-center text-slate-400">No data for these filters</td></tr>}
            {!loading && data?.rows?.map((r, i) => (
              <tr key={i} data-testid="sis-row">
                {dims.map((d) => <td key={d.key} className="font-medium text-slate-800 whitespace-nowrap">{r[d.key] ?? <span className="text-slate-400">(blank)</span>}</td>)}
                {cols.map((c) => <td key={c.key} className={`text-right tabular whitespace-nowrap ${c.type === "growth" ? growthCls(r[c.key]) : ""}`}>{fmtCell(r[c.key], c.type)}</td>)}
                {onDrill && <td className="w-8"><button title="Drill into this row" data-testid="sis-drill-btn" onClick={() => onDrill(r)} className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-[#E60000]"><CornerDownRight className="h-3.5 w-3.5" /></button></td>}
              </tr>
            ))}
            {!loading && data?.total && (
              <tr className="bg-[#E60000]/5 font-semibold sticky bottom-0" data-testid="sis-total-row">
                {dims.map((d, i) => <td key={d.key} className="text-slate-900">{i === 0 ? "Total" : ""}</td>)}
                {cols.map((c) => <td key={c.key} className={`text-right tabular ${c.type === "growth" ? growthCls(data.total[c.key]) : "text-slate-900"}`}>{fmtCell(data.total[c.key], c.type)}</td>)}
                {onDrill && <td />}
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between px-3 py-2 border-t border-slate-200 text-xs text-slate-500">
        <span data-testid="sis-count">{data?.count ?? 0} groups · page {data?.page ?? 1} of {data?.pages ?? 1} · {data?.meta?.rows_in_scope?.toLocaleString("en-IN")} source rows</span>
        <div className="flex gap-1">
          <button data-testid="sis-prev" disabled={page <= 1} onClick={() => onPage(page - 1)} className="p-1 rounded border disabled:opacity-40 hover:bg-slate-50"><ChevronLeft className="h-4 w-4" /></button>
          <button data-testid="sis-next" disabled={page >= (data?.pages || 1)} onClick={() => onPage(page + 1)} className="p-1 rounded border disabled:opacity-40 hover:bg-slate-50"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );
}
