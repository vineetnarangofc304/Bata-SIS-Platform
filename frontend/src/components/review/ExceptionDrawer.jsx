import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { X, Loader2 } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { fmtDate, shortId } from "@/lib/format";
import { StatusBadge } from "@/components/common/Badges";
import { inputCls, selectCls } from "@/components/common/DataTable";

export function ExceptionDrawer({ id, users, onClose, onChanged }) {
  const [e, setE] = useState(null);
  const [val, setVal] = useState("");
  const [comment, setComment] = useState("");
  const [assignee, setAssignee] = useState("");
  const [masterQ, setMasterQ] = useState("");
  const [masters, setMasters] = useState([]);
  const [newMaster, setNewMaster] = useState({});
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState(null);
  const nav = useNavigate();
  const load = () => api.get(`/exceptions/${id}`).then((r) => { setE(r.data); setVal(r.data.proposed_value ?? r.data.original_value ?? ""); });
  useEffect(() => { load(); setHistory(null); }, [id]); // eslint-disable-line
  const isMaster = e && ["store_code", "sku"].includes(e.field);
  useEffect(() => {
    if (!isMaster) return;
    const t = setTimeout(() => api.get(`/masters/${e.field === "store_code" ? "stores" : "skus"}`, { params: { search: masterQ || undefined, partner_code: e.field === "store_code" ? e.partner_code : undefined, page_size: 8 } }).then((r) => setMasters(r.data.items)), 250);
    return () => clearTimeout(t);
  }, [masterQ, isMaster, e?.field, e?.partner_code]);
  const act = async (action, extra = {}) => {
    setBusy(true);
    try { await api.post(`/exceptions/${id}/action`, { action, comment: comment || undefined, ...extra }); toast.success(`Action "${action.replace(/_/g, " ")}" applied`); setComment(""); await load(); onChanged(); } catch (ex) { toast.error(errMsg(ex)); } finally { setBusy(false); }
  };
  const showHistory = () => api.get(`/batches/${e.batch_id}/rows/${e.raw_row_id}/history`).then((r) => setHistory(r.data));
  if (!e) return null;
  const open = e.status === "open";
  const row = e.row;
  return (
    <div className="fixed inset-0 z-40 flex justify-end" data-testid="exception-drawer">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white h-full overflow-y-auto shadow-2xl fade-up">
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-start justify-between gap-4 z-10">
          <div><div className="flex items-center gap-2"><StatusBadge status={e.severity} /><span className="font-mono font-semibold text-slate-900">{e.rule_code}</span><StatusBadge status={e.status} testId="exception-status" /></div>
            <div className="text-xs text-slate-500 mt-1">{e.partner_name} · {e.file_name} · source row {e.source_row || e.row_index} · batch <button onClick={() => nav(`/batches/${e.batch_id}`)} className="font-mono underline">{shortId(e.batch_id)}</button> · row version v{row?.version} ({e.versions} total)</div></div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-100" data-testid="exception-drawer-close"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-6 space-y-6">
          <div className="rounded-md border bg-slate-50 p-4 text-sm"><div className="text-slate-800">{e.message}</div>
            <div className="grid grid-cols-2 gap-4 mt-3"><div><div className="label-caps">Original value ({e.field})</div><div className="font-mono text-red-700 mt-0.5 break-all" data-testid="exception-original-value">{e.original_value ?? "∅ (empty)"}</div></div><div><div className="label-caps">Proposed value</div><div className="font-mono text-emerald-700 mt-0.5 break-all" data-testid="exception-proposed-value">{e.proposed_value ?? "— none suggested —"}</div></div></div>
            {e.resolved_value !== undefined && <div className="mt-2 text-xs text-slate-600">Resolved with: <b className="font-mono">{String(e.resolved_value)}</b></div>}
          </div>
          {row && <div><div className="label-caps mb-2">Current row values (standardized · original shown when different)</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">{Object.entries(row.values).map(([k, v]) => { const o = row.original_values?.[k]; const diff = o !== null && o !== undefined && String(v) !== String(o); return <div key={k} className={`border rounded p-2 ${k === e.field ? "border-[#E60000] bg-red-50/40" : ""}`}><div className="text-slate-400">{k}</div><div className="font-mono text-slate-800 break-all">{v ?? "∅"}</div>{diff && <div className="text-[10px] text-slate-400 line-through break-all">{o}</div>}</div>; })}</div>
            {row.issues?.length > 1 && <div className="text-xs text-slate-500 mt-2">Other issues on this row: {row.issues.filter((i) => i.rule_code !== e.rule_code).map((i) => i.rule_code).join(", ")}</div>}
            <button onClick={showHistory} className="text-xs text-[#E60000] hover:underline mt-2" data-testid="exception-row-history-btn">View row version history</button>
            {history && <div className="mt-2 border rounded p-3 text-xs space-y-2 max-h-48 overflow-auto">{history.versions.map((v) => <div key={v.id} className="flex gap-2"><span className="font-mono text-slate-400 w-8">v{v.version}</span><StatusBadge status={v.status} /><span className="text-slate-600">{v.change_note} · {v.created_by} · {fmtDate(v.created_at)}</span></div>)}</div>}
          </div>}
          {open && (
            <div className="space-y-4" data-testid="exception-actions">
              <div className="label-caps">Resolve</div>
              <div className="flex flex-wrap gap-2">
                {e.proposed_value !== null && e.proposed_value !== undefined && <button data-testid="exception-accept-btn" disabled={busy} onClick={() => act("accept")} className="h-9 px-4 rounded-md btn-red text-xs font-semibold">Accept proposed value</button>}
                <div className="flex gap-1"><input data-testid="exception-correct-input" value={val} onChange={(ev) => setVal(ev.target.value)} className={inputCls + " h-9 w-48 font-mono text-xs"} placeholder={`New ${e.field}`} /><button data-testid="exception-correct-btn" disabled={busy || val === ""} onClick={() => act("correct", { value: String(val) })} className="h-9 px-3 rounded-md border text-xs font-semibold hover:bg-slate-50">Manual correct</button></div>
              </div>
              {isMaster && <div className="border rounded-md p-3 space-y-2">
                <div className="text-xs font-semibold text-slate-700">Map to existing {e.field === "store_code" ? "store" : "article"} (alias remembered)</div>
                <input data-testid="exception-master-search" value={masterQ} onChange={(ev) => setMasterQ(ev.target.value)} className={inputCls + " h-8 w-full text-xs"} placeholder="Search master by code or name…" />
                <div className="flex flex-wrap gap-1">{masters.map((m) => <button key={m.id} data-testid="exception-map-master-btn" disabled={busy} onClick={() => act("map_to_master", { value: m.code })} className="chip bg-slate-100 hover:bg-slate-900 hover:text-white px-2 py-1 font-normal"><b className="font-mono">{m.code}</b>&nbsp;{m.name}</button>)}</div>
                <div className="text-xs font-semibold text-slate-700 pt-2 border-t">Or add as new master record</div>
                <div className="flex flex-wrap gap-1"><input data-testid="exception-new-master-code" className={inputCls + " h-8 w-32 text-xs font-mono"} placeholder="code" value={newMaster.code ?? e.original_value ?? ""} onChange={(ev) => setNewMaster({ ...newMaster, code: ev.target.value })} /><input data-testid="exception-new-master-name" className={inputCls + " h-8 flex-1 text-xs"} placeholder="name" value={newMaster.name || ""} onChange={(ev) => setNewMaster({ ...newMaster, name: ev.target.value })} />{e.field === "sku" && <input className={inputCls + " h-8 w-32 text-xs"} placeholder="category" value={newMaster.category || ""} onChange={(ev) => setNewMaster({ ...newMaster, category: ev.target.value })} />}{e.field === "store_code" && <input className={inputCls + " h-8 w-28 text-xs"} placeholder="city" value={newMaster.city || ""} onChange={(ev) => setNewMaster({ ...newMaster, city: ev.target.value })} />}
                  <button data-testid="exception-add-master-btn" disabled={busy} onClick={() => act("add_master", { master_payload: { ...newMaster, code: newMaster.code ?? e.original_value } })} className="h-8 px-3 rounded-md border text-xs font-semibold hover:bg-slate-50">Add master & revalidate</button></div>
              </div>}
              <div className="flex flex-wrap gap-2 items-center">
                <input data-testid="exception-comment-input" value={comment} onChange={(ev) => setComment(ev.target.value)} className={inputCls + " h-9 flex-1 min-w-[200px] text-xs"} placeholder="Comment / justification (kept in history)" />
                <button data-testid="exception-comment-btn" disabled={busy || !comment} onClick={() => act("comment")} className="h-9 px-3 rounded-md border text-xs hover:bg-slate-50">Comment</button>
                <button data-testid="exception-ignore-btn" disabled={busy} onClick={() => act("ignore")} className="h-9 px-3 rounded-md border text-xs hover:bg-slate-50">Ignore issue</button>
                <button data-testid="exception-revalidate-btn" disabled={busy} onClick={() => act("revalidate")} className="h-9 px-3 rounded-md border text-xs hover:bg-slate-50">Revalidate</button>
                <button data-testid="exception-reject-row-btn" disabled={busy} onClick={() => act("reject_row")} className="h-9 px-3 rounded-md border border-red-200 text-red-700 text-xs hover:bg-red-50">Reject row</button>
                <button data-testid="exception-reject-file-btn" disabled={busy} onClick={() => window.confirm("Reject the entire file?") && act("reject_file")} className="h-9 px-3 rounded-md border border-red-200 text-red-700 text-xs hover:bg-red-50">Reject file</button>
              </div>
              <div className="flex gap-2 items-center"><select data-testid="exception-assign-select" value={assignee} onChange={(ev) => setAssignee(ev.target.value)} className={selectCls + " h-9 text-xs"}><option value="">Assign to…</option>{users.filter((u) => u.role !== "management").map((u) => <option key={u.username} value={u.username}>{u.name} ({u.username})</option>)}</select><button data-testid="exception-assign-btn" disabled={busy || !assignee} onClick={() => act("assign", { assignee })} className="h-9 px-3 rounded-md border text-xs hover:bg-slate-50">Assign</button>{e.assigned_to && <span className="text-xs text-slate-500">Currently: {e.assigned_to}</span>}</div>
              {busy && <div className="text-xs text-slate-400 flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />Applying…</div>}
            </div>
          )}
          <div><div className="label-caps mb-2">Action history</div>
            <ol className="space-y-1.5">{[...(e.history || [])].reverse().map((h, i) => <li key={i} className="text-xs flex gap-2" data-testid="exception-history-item"><span className="font-mono text-[#E60000] w-24 shrink-0">{h.action}</span><span className="text-slate-700 flex-1">{h.note}</span><span className="text-slate-400 whitespace-nowrap">{h.by} · {fmtDate(h.at)}</span></li>)}</ol>
            {e.comments?.length > 0 && <div className="mt-3 space-y-1">{e.comments.map((c, i) => <div key={i} className="text-xs bg-slate-50 border rounded p-2"><b>{c.by}</b> · {fmtDate(c.at)}<div>{c.text}</div></div>)}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
