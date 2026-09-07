import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function DataTable({ columns, rows, loading, page, pages, total, onPage, rowKey = "id", onRowClick, emptyText = "No records", testId, dense, footer }) {
  return (
    <div className="card overflow-hidden" data-testid={testId}>
      <div className="overflow-x-auto">
        <table className={cn("data-table w-full", dense && "text-xs")}>
          <thead><tr>{columns.map((c) => <th key={c.key} className={c.className} onClick={c.onSort} style={c.onSort ? { cursor: "pointer" } : {}}>{c.label}{c.sortIndicator}</th>)}</tr></thead>
          <tbody>
            {loading && <tr><td colSpan={columns.length} className="py-10 text-center text-slate-400"><Loader2 className="inline h-4 w-4 animate-spin mr-2" />Loading…</td></tr>}
            {!loading && rows?.length === 0 && <tr><td colSpan={columns.length} className="py-10 text-center text-slate-400">{emptyText}</td></tr>}
            {!loading && rows?.map((r, i) => (
              <tr key={r[rowKey] ?? i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cn(onRowClick && "cursor-pointer")} data-testid={testId ? `${testId}-row` : undefined}>
                {columns.map((c) => <td key={c.key} className={c.cellClass}>{c.render ? c.render(r, i) : r[c.key] ?? "—"}</td>)}
              </tr>
            ))}
            {footer}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between px-3 py-2 border-t border-slate-200 text-xs text-slate-500">
          <span data-testid={testId ? `${testId}-total` : undefined}>{total} records · page {page} of {pages}</span>
          <div className="flex gap-1">
            <button data-testid="table-prev-btn" disabled={page <= 1} onClick={() => onPage(page - 1)} className="p-1 rounded border disabled:opacity-40 hover:bg-slate-50"><ChevronLeft className="h-4 w-4" /></button>
            <button data-testid="table-next-btn" disabled={page >= pages} onClick={() => onPage(page + 1)} className="p-1 rounded border disabled:opacity-40 hover:bg-slate-50"><ChevronRight className="h-4 w-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, sub, actions, testId }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6 fade-up" data-testid={testId}>
      <div><h1 className="page-title">{title}</h1>{sub && <p className="page-sub">{sub}</p>}</div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function KpiCard({ label, value, sub, tone = "default", icon: Icon, testId, onClick }) {
  const tones = { default: "text-slate-900", red: "text-[#E60000]", green: "text-emerald-600", amber: "text-amber-600" };
  return (
    <div data-testid={testId} onClick={onClick} className={cn("card card-hover p-5 relative overflow-hidden", onClick && "cursor-pointer")}>
      <div className="flex items-start justify-between">
        <span className="label-caps">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-slate-400" />}
      </div>
      <div className={cn("font-display text-2xl sm:text-3xl font-bold mt-2 tabular", tones[tone])}>{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-1.5">{sub}</div>}
    </div>
  );
}

export function Field({ label, children, className }) {
  return <label className={cn("flex flex-col gap-1", className)}><span className="label-caps">{label}</span>{children}</label>;
}

export const inputCls = "h-9 rounded-md border border-slate-300 bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#E60000]/30 focus:border-[#E60000]";
export const selectCls = inputCls + " pr-8";
