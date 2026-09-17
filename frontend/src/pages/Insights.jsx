import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { TrendingUp, TrendingDown, Store, MailX, Percent, Layers, ShieldAlert, MessageCircleQuestion } from "lucide-react";
import { HelpLink } from "@/components/common/HelpLink";
import api from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { PageHeader } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";

const ICON = { sales_spike: TrendingUp, sales_drop: TrendingDown, underperformer: Store, missing_submission: MailX, discount_outlier: Percent, row_count_anomaly: Layers, data_quality: ShieldAlert };

export default function Insights() {
  const [d, setD] = useState(null);
  const [type, setType] = useState("");
  const nav = useNavigate();
  useEffect(() => { api.get("/insights").then((r) => setD(r.data)); }, []);
  const items = d?.items.filter((i) => !type || i.type === type) || [];
  const types = [...new Set(d?.items.map((i) => i.type) || [])];
  const go = (i) => { const p = new URLSearchParams(i.link.params || {}); nav(`${i.link.path}${p.toString() ? `?${p}` : ""}`); };
  return (
    <div data-testid="insights-page">
      <PageHeader title={<span className="flex items-center gap-2">Insights & Anomalies<HelpLink id="insights" /></span>} sub={d ? `Rule-based engine · ${d.engine} · generated ${fmtDate(d.generated_at)}` : "Rule-based statistical detection"} />
      <div className="flex flex-wrap gap-2 mb-4">
        <button data-testid="insight-filter-all" onClick={() => setType("")} className={`chip px-3 py-1.5 ${!type ? "bg-slate-900 text-white" : "bg-white border"}`}>All ({d?.items.length ?? 0})</button>
        {types.map((t) => <button key={t} data-testid={`insight-filter-${t}`} onClick={() => setType(t)} className={`chip px-3 py-1.5 ${type === t ? "bg-slate-900 text-white" : "bg-white border"}`}>{t.replace(/_/g, " ")} ({d.items.filter((i) => i.type === t).length})</button>)}
      </div>
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 stagger">
        {items.map((i) => { const I = ICON[i.type] || Layers; return (
          <button key={i.id} data-testid="insight-card" onClick={() => go(i)} className={`card card-hover p-5 text-left border-l-4 ${i.severity === "critical" ? "border-l-red-600" : i.severity === "warning" ? "border-l-amber-400" : "border-l-blue-400"}`}>
            <div className="flex items-start justify-between gap-2"><I className="h-4 w-4 text-slate-400 mt-0.5" /><StatusBadge status={i.severity} /></div>
            <div className="font-display font-semibold text-slate-900 mt-2">{i.title}</div>
            <div className="text-xs text-slate-600 mt-1">{i.description}</div>
            {i.metric && <div className="flex flex-wrap gap-2 mt-3">{Object.entries(i.metric).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => <span key={k} className="chip bg-slate-100 text-slate-600 font-normal">{k.replace(/_/g, " ")}: <b className="tabular">{typeof v === "number" ? v.toLocaleString("en-IN") : v}</b></span>)}</div>}
            <div className="text-[11px] text-[#E60000] mt-3 font-semibold">View underlying records →</div>
          </button>); })}
        {d && items.length === 0 && <div className="card p-8 text-center text-slate-400 text-sm col-span-full">No anomalies detected for this filter.</div>}
      </div>
      <Link to="/ask" className="card card-hover p-5 mt-6 flex items-start gap-4 border-[#E60000]/30 block" data-testid="nl-query-link">
        <MessageCircleQuestion className="h-6 w-6 text-[#E60000] shrink-0" />
        <div><div className="font-display font-semibold text-slate-900">Ask Bata Sales Data <StatusBadge status="active" className="ml-2" /></div><div className="text-xs text-slate-500 mt-1">Ask any question in plain English — e.g. "Which Lifestyle stores dropped more than 20% last week?" The analytics agent queries the same live data behind these insights and shows its workings.</div>
          <div className="mt-3 text-sm text-[#E60000] font-semibold">Open Ask Bata →</div></div>
      </Link>
    </div>
  );
}
