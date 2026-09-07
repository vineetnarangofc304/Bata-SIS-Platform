import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { PageHeader, Field, inputCls, selectCls } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";
import { useAuth } from "@/context/AuthContext";

export default function Settings() {
  const [s, setS] = useState(null);
  const [integ, setInteg] = useState([]);
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const { user } = useAuth();
  useEffect(() => { api.get("/settings").then((r) => setS(r.data)); api.get("/integrations").then((r) => setInteg(r.data)); }, []);
  const save = async () => { try { await api.put("/settings", s); toast.success("Settings saved (audited)"); } catch (e) { toast.error(errMsg(e)); } };
  const changePw = async () => { try { await api.post("/auth/change-password", pw); toast.success("Password changed"); setPw({ current_password: "", new_password: "" }); } catch (e) { toast.error(errMsg(e)); } };
  if (!s) return null;
  return (
    <div data-testid="settings-page">
      <PageHeader title="Settings" sub="Confidence thresholds, blocking behaviour, restatement policy and Phase-2 integration switches." actions={<button data-testid="settings-save-btn" onClick={save} className="h-9 px-4 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Save className="h-3.5 w-3.5" />Save</button>} />
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card p-5 space-y-4" data-testid="settings-thresholds">
          <h3 className="font-display font-semibold">Recognition confidence thresholds</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="High ≥ (auto-accept)"><input data-testid="settings-threshold-high" type="number" value={s.thresholds.high} onChange={(e) => setS({ ...s, thresholds: { ...s.thresholds, high: Number(e.target.value) } })} className={inputCls} /></Field>
            <Field label="Medium ≥ (below = low → stop & review)"><input data-testid="settings-threshold-medium" type="number" value={s.thresholds.medium} onChange={(e) => setS({ ...s, thresholds: { ...s.thresholds, medium: Number(e.target.value) } })} className={inputCls} /></Field>
            <Field label="Medium confidence behaviour" className="col-span-2"><select data-testid="settings-medium-behavior" value={s.medium_behavior} onChange={(e) => setS({ ...s, medium_behavior: e.target.value })} className={selectCls}><option value="review">Stop and route to Review Queue</option><option value="proceed">Proceed with warning (mapping still recorded for audit)</option></select></Field>
            <Field label="Restatement policy" className="col-span-2"><select data-testid="settings-restatement" value={s.restatement_mode} onChange={(e) => setS({ ...s, restatement_mode: e.target.value })} className={selectCls}><option value="review_then_supersede">Route to review; on approval supersede prior batch (default)</option><option value="auto_supersede" disabled>Auto-supersede (not enabled)</option></select></Field>
            <Field label="Max file size (MB)"><input type="number" value={s.max_file_mb} onChange={(e) => setS({ ...s, max_file_mb: Number(e.target.value) })} className={inputCls} /></Field>
            <Field label="Currency"><input disabled value="INR" className={inputCls + " bg-slate-50"} /></Field>
          </div>
          <div className="text-xs text-slate-500 border-t pt-3">Financial corrections never apply silently — even at 100% confidence, proposed values require operator acceptance in the Review Queue.</div>
        </div>
        <div className="space-y-5">
          <div className="card p-5" data-testid="settings-integrations">
            <h3 className="font-display font-semibold mb-3">Phase-2 modules</h3>
            <div className="space-y-2">{integ.map((i) => <div key={i.key} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0"><div><div className="text-sm font-medium text-slate-800">{i.name}</div><div className="text-xs text-slate-500">{i.detail}</div></div><div className="flex flex-col items-end gap-1"><StatusBadge status={i.status} /><label className="text-[11px] text-slate-500 flex items-center gap-1"><input type="checkbox" data-testid={`feature-${i.key}`} checked={!!s.features?.[i.key]} onChange={(e) => setS({ ...s, features: { ...s.features, [i.key]: e.target.checked } })} className="accent-[#E60000]" />enabled flag</label></div></div>)}</div>
          </div>
          <div className="card p-5" data-testid="settings-channels">
            <h3 className="font-display font-semibold mb-3">Notification channels</h3>
            <div className="flex gap-4 text-sm">{["in_app", "email", "whatsapp"].map((c) => <label key={c} className="flex items-center gap-2"><input type="checkbox" disabled={c !== "in_app"} checked={!!s.notification_channels?.[c]} onChange={(e) => setS({ ...s, notification_channels: { ...s.notification_channels, [c]: e.target.checked } })} className="accent-[#E60000]" />{c.replace("_", "-")}{c !== "in_app" && <StatusBadge status="awaiting_credentials" />}</label>)}</div>
          </div>
          <div className="card p-5" data-testid="settings-password">
            <h3 className="font-display font-semibold mb-3">Change my password ({user.username})</h3>
            <div className="grid grid-cols-2 gap-3"><Field label="Current"><input type="password" data-testid="pw-current" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} className={inputCls} /></Field><Field label="New (min 8)"><input type="password" data-testid="pw-new" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} className={inputCls} /></Field></div>
            <button data-testid="pw-save" onClick={changePw} className="mt-3 h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50">Update password</button>
          </div>
        </div>
      </div>
    </div>
  );
}
