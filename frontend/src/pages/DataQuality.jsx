import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import api from "@/lib/api";
import { num, pct } from "@/lib/format";
import { PageHeader, DataTable } from "@/components/common/DataTable";
import { StatusBadge, ConfidenceBadge } from "@/components/common/Badges";

export default function DataQuality() {
  const [d, setD] = useState(null);
  const nav = useNavigate();
  useEffect(() => { api.get("/data-quality").then((r) => setD(r.data)); }, []);
  if (!d) return <div className="text-slate-400 text-sm">Loading…</div>;
  return (
    <div data-testid="data-quality-page">
      <PageHeader title="Data Quality" sub="Acceptance rates, recognition confidence and exception mix per partner." />
      <div className="card p-5 mb-4" data-testid="dq-trend-chart">
        <h3 className="font-display font-semibold mb-3">Rows accepted vs rejected per day (30d)</h3>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={d.trend}><CartesianGrid stroke="#eef2f7" vertical={false} /><XAxis dataKey="date" tickFormatter={(v) => v.slice(5)} fontSize={11} stroke="#94a3b8" /><YAxis fontSize={11} stroke="#94a3b8" width={40} /><Tooltip /><Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="accepted" stackId="a" fill="#16A34A" name="Accepted" /><Bar dataKey="warning" stackId="a" fill="#D97706" name="Warnings" /><Bar dataKey="rejected" stackId="a" fill="#DC2626" name="Rejected" /><Bar dataKey="duplicate" stackId="a" fill="#94a3b8" name="Duplicate" radius={[3, 3, 0, 0]} /></BarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid xl:grid-cols-[1fr_380px] gap-4">
        <DataTable testId="dq-partner-table" columns={[
          { key: "partner_name", label: "Partner", render: (r) => <span className="font-medium">{r.partner_name}</span> },
          { key: "batches", label: "Batches", render: (r) => num(r.batches) }, { key: "total", label: "Rows", render: (r) => num(r.total) },
          { key: "acceptance_pct", label: "Acceptance", render: (r) => <span className={`font-semibold tabular ${r.acceptance_pct >= 98 ? "text-emerald-600" : r.acceptance_pct >= 90 ? "text-amber-600" : "text-red-600"}`}>{pct(r.acceptance_pct)}</span> },
          { key: "rejected", label: "Rejected", render: (r) => <span className="text-red-600 tabular">{num(r.rejected)}</span> }, { key: "warning", label: "Warnings", render: (r) => num(r.warning) }, { key: "duplicate", label: "Dupes", render: (r) => num(r.duplicate) },
          { key: "avg_confidence", label: "Avg confidence", render: (r) => <ConfidenceBadge value={Math.round(r.avg_confidence)} /> },
        ]} rows={d.by_partner} onRowClick={(r) => nav(`/batches?partner_code=${r.partner_code}`)} />
        <div className="card p-5 h-fit" data-testid="dq-rules">
          <h3 className="font-display font-semibold mb-3">Exceptions by rule</h3>
          <div className="space-y-2">{d.by_rule.map((r) => <button key={r.rule_code} onClick={() => nav(`/review?rule_code=${r.rule_code}`)} className="w-full flex items-center justify-between text-xs hover:bg-slate-50 rounded px-1 py-1"><span className="flex items-center gap-2"><StatusBadge status={r.severity} /><span className="font-mono">{r.rule_code}</span></span><span className="tabular text-slate-600">{r.open} open / {r.total}</span></button>)}{d.by_rule.length === 0 && <div className="text-xs text-slate-400">No exceptions recorded.</div>}</div>
        </div>
      </div>
    </div>
  );
}
