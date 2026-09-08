import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { IndianRupee, Store, CheckCircle2, AlertTriangle } from "lucide-react";
import api from "@/lib/api";
import { inr, num, pct, fmtDate } from "@/lib/format";
import { KpiCard, PageHeader, selectCls } from "@/components/common/DataTable";
import { StatusBadge, Counts, ConfidenceBadge } from "@/components/common/Badges";

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [partners, setPartners] = useState([]);
  const [partner, setPartner] = useState("");
  const nav = useNavigate();
  useEffect(() => { api.get("/partners").then((r) => setPartners(r.data)); }, []);
  useEffect(() => { api.get("/dashboard", { params: partner ? { partner_code: partner } : {} }).then((r) => setD(r.data)); }, [partner]);
  if (!d) return <div className="text-slate-400 text-sm">Loading dashboard…</div>;
  const k = d.kpis;
  return (
    <div data-testid="dashboard-page">
      <PageHeader title="Dashboard" sub="Consolidated SIS sales across all partners · INR" actions={
        <select data-testid="dashboard-partner-filter" value={partner} onChange={(e) => setPartner(e.target.value)} className={selectCls}><option value="">All partners</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select>} />
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 stagger">
        <KpiCard testId="dashboard-kpi-total-sales" label={`SIS Sales · ${k.month}`} value={inr(k.mtd_sales, { compact: true })} icon={IndianRupee} tone="red" sub={`${num(k.mtd_qty)} pairs · ${num(k.mtd_txns)} lines · data as of ${d.as_of}`} />
        <KpiCard testId="dashboard-kpi-target" label="Week 32 target achievement" value={k.achievement_pct !== null ? pct(k.achievement_pct) : "—"} icon={Store} tone={k.achievement_pct >= 100 ? "green" : "amber"} sub={`${inr(k.actual_wk, { compact: true })} actual vs ${inr(k.target_wk, { compact: true })} target · ${k.active_partners}/${k.total_partners} partners submitted`} onClick={() => nav("/reports?report=target_vs_actual")} />
        <KpiCard testId="dashboard-kpi-accepted-ratio" label="Accepted record ratio (30d)" value={pct(k.acceptance_pct)} icon={CheckCircle2} tone="green" sub={`${num(k.accepted_30d)} / ${num(k.rows_30d)} rows · ${k.batches_30d} batches`} />
        <KpiCard testId="dashboard-kpi-exceptions" label="Pending action" value={num(k.open_exceptions)} icon={AlertTriangle} tone={k.open_exceptions ? "amber" : "default"} sub={`open exceptions · ${k.awaiting_review} batch(es) awaiting review`} onClick={() => nav("/review")} />
      </div>
      <div className="grid xl:grid-cols-3 gap-4 mt-4">
        <div className="card p-5 xl:col-span-2" data-testid="dashboard-sales-trend-chart">
          <div className="flex items-center justify-between mb-3"><h3 className="font-display font-semibold">Weekly net sales · Bata weeks (2025 → Wk32 2026)</h3><span className="text-xs text-slate-400">INR · as of {d.as_of}</span></div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={d.weekly}><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#E60000" stopOpacity={0.35} /><stop offset="100%" stopColor="#E60000" stopOpacity={0} /></linearGradient></defs>
              <CartesianGrid stroke="#eef2f7" vertical={false} /><XAxis dataKey="week" tickFormatter={(v) => v.slice(2)} fontSize={11} stroke="#94a3b8" /><YAxis tickFormatter={(v) => inr(v, { compact: true })} fontSize={11} stroke="#94a3b8" width={70} />
              <Tooltip formatter={(v) => inr(v)} labelStyle={{ fontSize: 12 }} /><Area type="monotone" dataKey="net" stroke="#E60000" strokeWidth={2} fill="url(#g)" name="Net sales" /></AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="card p-5" data-testid="dashboard-partner-chart">
          <h3 className="font-display font-semibold mb-3">Sales by partner · last 30 days of data</h3>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.by_partner} layout="vertical" margin={{ left: 10 }}><XAxis type="number" hide /><YAxis type="category" dataKey="partner" width={110} fontSize={11} stroke="#64748b" /><Tooltip formatter={(v) => inr(v)} /><Bar dataKey="net" fill="#111827" radius={[0, 3, 3, 0]} name="Net" /></BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid xl:grid-cols-3 gap-4 mt-4">
        <div className="card p-5" data-testid="dashboard-dq-chart">
          <h3 className="font-display font-semibold mb-3">Data quality · latest submissions by partner</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.dq_trend}><CartesianGrid stroke="#eef2f7" vertical={false} /><XAxis dataKey="date" tickFormatter={(v) => String(v).slice(0, 9)} fontSize={10} stroke="#94a3b8" interval={0} angle={-20} textAnchor="end" height={40} /><YAxis fontSize={11} stroke="#94a3b8" width={40} /><Tooltip /><Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="accepted" stackId="a" fill="#16A34A" name="Accepted" /><Bar dataKey="rejected" stackId="a" fill="#DC2626" name="Rejected" /><Bar dataKey="duplicate" stackId="a" fill="#94a3b8" name="Duplicate" radius={[3, 3, 0, 0]} /></BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card p-5" data-testid="dashboard-category">
          <h3 className="font-display font-semibold mb-3">Category mix · 30 days</h3>
          <div className="space-y-2">
            {d.by_category.map((c) => { const max = d.by_category[0]?.net || 1; return (
              <div key={c.category} className="text-xs"><div className="flex justify-between mb-0.5"><span className="text-slate-700">{c.category || "Unclassified"}</span><span className="tabular text-slate-500">{inr(c.net, { compact: true })}</span></div><div className="h-1.5 bg-slate-100 rounded"><div className="h-full bg-[#E60000] rounded" style={{ width: `${(c.net / max) * 100}%` }} /></div></div>); })}
          </div>
        </div>
        <div className="card p-5" data-testid="dashboard-top-skus">
          <h3 className="font-display font-semibold mb-3">Top articles · 30 days</h3>
          <table className="w-full text-xs"><tbody>{d.top_skus.map((s, i) => <tr key={s.sku} className="border-b border-slate-100 last:border-0"><td className="py-1.5 text-slate-400 w-5">{i + 1}</td><td className="py-1.5"><div className="text-slate-800 font-medium">{s.name}</div><div className="font-mono text-slate-400">{s.sku}</div></td><td className="py-1.5 text-right tabular text-slate-700">{inr(s.net, { compact: true })}<div className="text-slate-400">{s.qty} pairs</div></td></tr>)}</tbody></table>
        </div>
      </div>
      <div className="card mt-4" data-testid="dashboard-recent-batches">
        <div className="flex items-center justify-between px-5 py-3 border-b"><h3 className="font-display font-semibold">Recent ingestion batches</h3><button onClick={() => nav("/batches")} className="text-xs text-[#E60000] hover:underline">View all →</button></div>
        <table className="data-table w-full"><thead><tr><th>File</th><th>Partner</th><th>Status</th><th>Rows</th><th>Confidence</th><th>Received</th></tr></thead>
          <tbody>{d.recent_batches.map((b) => <tr key={b.id} className="cursor-pointer" onClick={() => nav(`/batches/${b.id}`)}><td className="font-medium text-slate-800 max-w-xs truncate">{b.file_name}</td><td>{b.partner_name || "—"}</td><td><StatusBadge status={b.status} /></td><td><Counts counts={b.counts} /></td><td><ConfidenceBadge value={b.confidence} /></td><td className="text-slate-500 text-xs">{fmtDate(b.created_at)}</td></tr>)}</tbody></table>
      </div>
    </div>
  );
}
