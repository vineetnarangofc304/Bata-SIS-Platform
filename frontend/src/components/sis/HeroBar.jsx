import { inr, num } from "@/lib/format";
import { HelpLink } from "@/components/common/HelpLink";

export const growth = (v, d = 1) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
export const growthCls = (v) => (v === null || v === undefined ? "text-slate-400" : v >= 0 ? "text-emerald-600" : "text-red-600");
export const fmtCell = (v, t) => {
  if (v === null || v === undefined) return "—";
  if (t === "money") return inr(v, { decimals: 0 });
  if (t === "int") return num(Math.round(v));
  if (t === "num1") return Number(v).toFixed(1);
  if (t === "pct") return `${(v * 100).toFixed(1)}%`;
  if (t === "growth") return growth(v);
  return v;
};

function Hero({ label, value, sub, tone, helpId, testId }) {
  return (
    <div className="card p-4 min-w-0" data-testid={testId}>
      <div className="label-caps flex items-center gap-1 truncate">{label}{helpId && <HelpLink id={helpId} />}</div>
      <div className={`font-display text-xl xl:text-2xl font-bold mt-1 tabular truncate ${tone || "text-slate-900"}`}>{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-1 truncate">{sub}</div>}
    </div>
  );
}

export function HeroBar({ t, meta }) {
  if (!t) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-3 stagger" data-testid="sis-hero-bar">
      <Hero testId="sis-hero-nsv26" label="NSV-26" value={inr(t.nsv_26, { compact: true })} sub={`vs NSV-25 ${inr(t.nsv_25, { compact: true })}`} tone="text-[#E60000]" helpId="s-nsv" />
      <Hero testId="sis-hero-nsvg" label="NSV Growth" value={growth(t.nsv_g)} sub={`LTL growth ${growth(t.ltl_g)}`} tone={growthCls(t.nsv_g)} helpId="s-nsv-g" />
      <Hero testId="sis-hero-est" label="EST (Target)" value={inr(t.est, { compact: true })} sub={`EST G ${growth(t.est_g)}`} tone={growthCls(t.est_g)} helpId="s-est" />
      <Hero testId="sis-hero-str" label="#STR-26" value={num(t.str_26)} sub={`#STR-25 ${num(t.str_25)} · stores with sales`} helpId="s-str" />
      <Hero testId="sis-hero-panel" label="#PANEL-26" value={Number(t.panel_26 || 0).toFixed(1)} sub={`#PANEL-25 ${Number(t.panel_25 || 0).toFixed(1)} · HP MEN = 1.4`} helpId="s-panel" />
      <Hero testId="sis-hero-prod" label="PROD/WK-26" value={inr(t.prod_wk_26, { decimals: 0 })} sub={`PROD/WK-25 ${inr(t.prod_wk_25, { decimals: 0 })}`} helpId="s-prod" />
      <Hero testId="sis-hero-qty" label="QTY-26 (pairs)" value={num(t.qty_26)} sub={`QTY G ${growth(t.qty_g)} · ASP ${inr(t.asp_26, { decimals: 0 })}`} tone={growthCls(t.qty_g)} helpId="s-qty" />
      <Hero testId="sis-hero-period" label="Data window" value={meta?.latest_week ? `Wk ${meta.latest_week}` : "—"} sub={`latest till-date week · ${meta?.latest_month || ""} · ${num(meta?.rows_in_scope)} rows in scope`} helpId="s-till-date" />
    </div>
  );
}
