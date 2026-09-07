import { cn } from "@/lib/utils";

const STATUS = {
  "Received": "bg-slate-100 text-slate-700 border-slate-200",
  "Analysing": "bg-blue-50 text-blue-700 border-blue-200",
  "Awaiting Review": "bg-amber-50 text-amber-700 border-amber-200",
  "Validating": "bg-blue-50 text-blue-700 border-blue-200",
  "Partially Processed": "bg-amber-50 text-amber-800 border-amber-200",
  "Successfully Processed": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Failed": "bg-red-50 text-red-700 border-red-200",
  "Rejected": "bg-red-50 text-red-700 border-red-200",
  "Reprocessed": "bg-indigo-50 text-indigo-700 border-indigo-200",
  "Superseded": "bg-slate-100 text-slate-500 border-slate-200",
  open: "bg-amber-50 text-amber-700 border-amber-200", accepted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  corrected: "bg-emerald-50 text-emerald-700 border-emerald-200", resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ignored: "bg-slate-100 text-slate-600 border-slate-200", rejected: "bg-red-50 text-red-700 border-red-200",
  warning: "bg-amber-50 text-amber-700 border-amber-200", duplicate: "bg-slate-100 text-slate-600 border-slate-200",
  Info: "bg-blue-50 text-blue-700 border-blue-200", Warning: "bg-amber-50 text-amber-700 border-amber-200",
  Error: "bg-red-50 text-red-700 border-red-200", Critical: "bg-red-600 text-white border-red-700",
  info: "bg-blue-50 text-blue-700 border-blue-200", critical: "bg-red-50 text-red-700 border-red-200", success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  active: "bg-emerald-50 text-emerald-700 border-emerald-200", inactive: "bg-slate-100 text-slate-500 border-slate-200",
  awaiting_credentials: "bg-amber-50 text-amber-700 border-amber-200", deferred: "bg-slate-100 text-slate-600 border-slate-200",
  interface_ready: "bg-blue-50 text-blue-700 border-blue-200", configured_inactive: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

export function StatusBadge({ status, className, testId }) {
  const s = String(status ?? "—");
  return (
    <span data-testid={testId} className={cn("inline-flex items-center whitespace-nowrap rounded border px-2 py-0.5 text-[11px] font-semibold", STATUS[s] || "bg-slate-100 text-slate-600 border-slate-200", className)}>
      {s.replace(/_/g, " ")}
    </span>
  );
}

export function ConfidenceBadge({ value, level, testId }) {
  if (value === null || value === undefined) return <span className="text-slate-400 text-xs">—</span>;
  const lv = level || (value >= 90 ? "high" : value >= 70 ? "medium" : "low");
  const color = lv === "high" ? "bg-emerald-500" : lv === "medium" ? "bg-amber-500" : "bg-red-500";
  return (
    <span data-testid={testId} className="inline-flex items-center gap-2" title={`${lv} confidence`}>
      <span className="h-1.5 w-14 rounded-full bg-slate-200 overflow-hidden"><span className={cn("block h-full rounded-full", color)} style={{ width: `${value}%` }} /></span>
      <span className="tabular text-xs font-semibold text-slate-700">{value}%</span>
    </span>
  );
}

export function Counts({ counts, testId }) {
  if (!counts) return null;
  const items = [["total", "bg-slate-100 text-slate-700", "Total"], ["accepted", "bg-emerald-50 text-emerald-700", "Accepted"], ["warning", "bg-amber-50 text-amber-700", "Warning"], ["rejected", "bg-red-50 text-red-700", "Rejected"], ["duplicate", "bg-slate-100 text-slate-500", "Duplicate"]];
  return (
    <span data-testid={testId} className="inline-flex gap-1">
      {items.map(([k, c, t]) => <span key={k} title={t} className={cn("chip", c)}>{counts[k] ?? 0}</span>)}
    </span>
  );
}
