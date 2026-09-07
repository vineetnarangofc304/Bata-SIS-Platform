import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, CheckCheck } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { ConfidenceBadge } from "@/components/common/Badges";
import { selectCls } from "@/components/common/DataTable";

export function MappingReview({ batch, onDone }) {
  const { isOps } = useAuth();
  const [fields, setFields] = useState([]);
  const [partners, setPartners] = useState([]);
  const [rows, setRows] = useState([]);
  const [remember, setRemember] = useState(true);
  const [partner, setPartner] = useState(batch.partner_code || "");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/fields").then((r) => setFields(r.data)); api.get("/partners").then((r) => setPartners(r.data)); }, []);
  useEffect(() => { setRows(batch.column_mappings.map((c) => ({ ...c, field: c.proposed_field || "", action: c.action || (c.proposed_field ? "map" : "ignore") }))); setPartner(batch.partner_code || ""); }, [batch]);
  const editable = isOps && batch.status === "Awaiting Review" && !batch.restatement_of;
  const setField = (i, field) => setRows((rs) => rs.map((r, k) => k === i ? { ...r, field, action: field ? "map" : "ignore", overridden: field !== (r.proposed_field || "") } : r));
  const mapped = new Set(rows.filter((r) => r.action === "map" && r.field).map((r) => r.field));
  const required = fields.filter((f) => f.required);
  const missing = required.filter((f) => !mapped.has(f.key));
  const dupes = rows.filter((r) => r.field && r.action === "map").map((r) => r.field).filter((f, i, a) => a.indexOf(f) !== i);
  const approve = async () => {
    if (!partner) return toast.error("Select the partner first");
    if (missing.length) return toast.error(`Map required fields: ${missing.map((m) => m.label).join(", ")}`);
    if (dupes.length) return toast.error(`Field mapped twice: ${dupes.join(", ")}`);
    setBusy(true);
    try { await api.post(`/batches/${batch.id}/approve-mapping`, { mappings: rows.map((r) => ({ source_column: r.source_column, field: r.field || null, action: r.action })), remember, partner_code: partner }); toast.success(remember ? "Mapping approved and remembered for this partner" : "Mapping approved"); onDone(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="card" data-testid="mapping-review-table">
      <div className="flex flex-wrap items-center gap-4 px-5 py-3 border-b bg-slate-50 text-xs">
        <label className="flex items-center gap-2"><span className="label-caps">Partner</span>
          <select data-testid="mapping-partner-select" disabled={!editable} value={partner} onChange={(e) => setPartner(e.target.value)} className={selectCls + " h-8"}><option value="">— select —</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></label>
        <span className="text-slate-500">{mapped.size} of {rows.length} columns mapped · required missing: {missing.length ? <span className="text-red-600 font-semibold" data-testid="mapping-missing-required">{missing.map((m) => m.label).join(", ")}</span> : <span className="text-emerald-600 font-semibold">none</span>}</span>
        {editable && <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-1.5 cursor-pointer"><input type="checkbox" data-testid="mapping-remember-checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="accent-[#E60000]" />Remember for future {partner ? partners.find((p) => p.code === partner)?.name : "partner"} files</label>
          <button data-testid="mapping-approve-all-btn" disabled={busy} onClick={approve} className="h-8 px-4 rounded-md btn-red font-semibold flex items-center gap-1.5">{busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCheck className="h-3.5 w-3.5" />}Approve mapping & validate</button>
        </div>}
      </div>
      <div className="overflow-x-auto">
        <table className="data-table w-full">
          <thead><tr><th>#</th><th>Incoming column</th><th>Sample values</th><th>Bata field</th><th>Confidence</th><th>Reason</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.source_column} data-testid="mapping-row" className={r.action === "ignore" ? "opacity-60" : ""}>
                <td className="font-mono text-slate-400">{r.index + 1}</td>
                <td className="font-medium text-slate-800 whitespace-nowrap">{r.source_column}<div className="text-[10px] text-slate-400 font-normal">type: {r.inferred_type}</div></td>
                <td><div className="flex flex-wrap gap-1 max-w-xs">{r.sample_values?.slice(0, 4).map((s, k) => <span key={k} className="chip bg-slate-100 text-slate-600 font-mono font-normal max-w-[120px] truncate" title={s}>{s}</span>)}</div></td>
                <td>{editable ? <select data-testid="mapping-override-dropdown" value={r.field} onChange={(e) => setField(i, e.target.value)} className={`${selectCls} h-8 text-xs ${r.overridden ? "border-[#E60000]" : ""}`}><option value="">— ignore column —</option>{fields.map((f) => <option key={f.key} value={f.key}>{f.label}{f.required ? " *" : ""}{mapped.has(f.key) && f.key !== r.field ? " (used)" : ""}</option>)}</select>
                  : r.field ? <span className="chip bg-slate-900 text-white font-mono">{r.field}</span> : <span className="text-xs text-slate-400 italic">ignored</span>}</td>
                <td><ConfidenceBadge value={r.confidence} /></td>
                <td className="text-xs text-slate-500 max-w-sm">{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
