import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Plus, Download, Upload as UploadIcon, Pencil, History } from "lucide-react";
import api, { errMsg, downloadFile } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { DataTable, PageHeader, inputCls, selectCls, Field } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const TABS = {
  stores: { label: "Stores / SIS", fields: ["partner_code", "code", "name", "city", "region", "state", "aliases", "active"] },
  skus: { label: "SKU / Articles", fields: ["code", "name", "category", "sub_category", "brand", "gender", "mrp", "aliases", "active"] },
  hierarchy: { label: "Product hierarchy", fields: ["code", "division", "category", "brands", "active"] },
  geo: { label: "Geo mapping", fields: ["city", "region", "state", "active"] },
  aliases: { label: "Alias dictionary", fields: ["field", "alias", "partner_code", "source", "active"] },
  rules: { label: "Validation rules", fields: ["code", "name", "severity", "blocking", "enabled", "params", "description"] },
  sender_rules: { label: "Sender rules", fields: ["partner_code", "match_type", "pattern", "priority", "active"] },
};
const LIST_FIELDS = ["aliases", "brands"];

export default function Masters({ fixedTab }) {
  const [tab, setTab] = useState(fixedTab || "stores");
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [edit, setEdit] = useState(null);
  const [versions, setVersions] = useState(null);
  const [fields, setFields] = useState([]);
  const [partners, setPartners] = useState([]);
  const fileRef = useRef();
  const load = useCallback(() => api.get(`/masters/${tab}`, { params: { page, page_size: 25, search: search || undefined } }).then((r) => setData(r.data)), [tab, page, search]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/fields").then((r) => setFields(r.data)); api.get("/partners").then((r) => setPartners(r.data)); }, []);
  const spec = TABS[tab];
  const save = async () => {
    const body = { ...edit };
    LIST_FIELDS.forEach((k) => { if (typeof body[k] === "string") body[k] = body[k].split(",").map((s) => s.trim()).filter(Boolean); });
    if (typeof body.params === "string") { try { body.params = JSON.parse(body.params || "{}"); } catch { return toast.error("Params must be valid JSON"); } }
    if (body.mrp !== undefined && body.mrp !== "") body.mrp = Number(body.mrp);
    if (body.priority !== undefined) body.priority = Number(body.priority);
    try { if (body.id) await api.put(`/masters/${tab}/${body.id}`, body); else await api.post(`/masters/${tab}`, body); toast.success("Saved — new version recorded"); setEdit(null); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  const toggle = async (r, k) => { try { await api.put(`/masters/${tab}/${r.id}`, { [k]: !r[k] }); load(); } catch (e) { toast.error(errMsg(e)); } };
  const imp = async (f) => { if (!f) return; const fd = new FormData(); fd.append("file", f); try { const { data: r } = await api.post(`/masters/${tab}/import`, fd); toast.success(`Imported: ${r.created} created, ${r.updated} updated`); load(); } catch (e) { toast.error(errMsg(e)); } };
  const render = (k) => (r) => {
    const v = r[k];
    if (k === "active" || k === "enabled" || k === "blocking") return <button data-testid={`master-toggle-${k}`} onClick={(e) => { e.stopPropagation(); toggle(r, k); }}><StatusBadge status={v ? (k === "blocking" ? "Error" : "active") : (k === "blocking" ? "Warning" : "inactive")} /></button>;
    if (k === "severity") return <StatusBadge status={v} />;
    if (Array.isArray(v)) return v.length ? <div className="flex flex-wrap gap-1">{v.map((x) => <span key={x} className="chip bg-slate-100 text-slate-600 font-normal">{x}</span>)}</div> : <span className="text-slate-300">—</span>;
    if (typeof v === "object" && v) return <code className="text-[11px]">{JSON.stringify(v)}</code>;
    if (k === "code" || k === "alias" || k === "pattern") return <span className="font-mono text-xs font-semibold">{v}</span>;
    return v ?? <span className="text-slate-300">—</span>;
  };
  const cols = [...spec.fields.map((k) => ({ key: k, label: k.replace(/_/g, " "), render: render(k) })), { key: "version", label: "v", render: (r) => <span className="text-xs text-slate-400 tabular">v{r.version || 1}</span> }, { key: "act", label: "", render: (r) => <div className="flex gap-1"><button data-testid="master-edit-btn" onClick={(e) => { e.stopPropagation(); setEdit({ ...r, ...Object.fromEntries(LIST_FIELDS.filter((f) => Array.isArray(r[f])).map((f) => [f, r[f].join(", ")])), params: r.params ? JSON.stringify(r.params) : undefined }); }} className="p-1 rounded hover:bg-slate-100"><Pencil className="h-3.5 w-3.5 text-slate-500" /></button><button data-testid="master-versions-btn" onClick={(e) => { e.stopPropagation(); api.get(`/masters/${tab}/${r.id}/versions`).then((x) => setVersions({ item: r, list: x.data })); }} className="p-1 rounded hover:bg-slate-100"><History className="h-3.5 w-3.5 text-slate-500" /></button></div> }];
  const input = (k) => {
    const v = edit[k] ?? "";
    if (["active", "enabled", "blocking"].includes(k)) return <select data-testid={`master-form-${k}`} value={String(v === "" ? true : v)} onChange={(e) => setEdit({ ...edit, [k]: e.target.value === "true" })} className={selectCls}><option value="true">Yes</option><option value="false">No</option></select>;
    if (k === "partner_code") return <select data-testid="master-form-partner_code" value={v} onChange={(e) => setEdit({ ...edit, [k]: e.target.value || null })} className={selectCls}><option value="">{tab === "aliases" ? "Global (all partners)" : "— select —"}</option>{partners.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select>;
    if (k === "field") return <select data-testid="master-form-field" value={v} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} className={selectCls}><option value="">— Bata field —</option>{fields.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}</select>;
    if (k === "severity") return <select data-testid="master-form-severity" value={v} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} className={selectCls}>{["Info", "Warning", "Error", "Critical"].map((s) => <option key={s}>{s}</option>)}</select>;
    if (k === "match_type") return <select value={v} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} className={selectCls}>{["sender_domain", "sender_email", "subject", "attachment_name", "content"].map((s) => <option key={s}>{s}</option>)}</select>;
    return <input data-testid={`master-form-${k}`} value={v} onChange={(e) => setEdit({ ...edit, [k]: e.target.value })} className={inputCls} placeholder={LIST_FIELDS.includes(k) ? "comma separated" : k === "params" ? '{"max_pct": 60}' : ""} />;
  };
  return (
    <div data-testid="masters-page">
      {!fixedTab && <PageHeader title="Masters" sub="Reference data that drives recognition and validation. Every edit is versioned; nothing is deleted — deactivate instead." />}
      {!fixedTab && <div className="flex flex-wrap gap-1 mb-4 border-b">{Object.entries(TABS).map(([k, t]) => <button key={k} data-testid={`masters-tab-${k}`} onClick={() => { setTab(k); setPage(1); setSearch(""); }} className={`px-3 py-2 text-[13px] font-medium border-b-2 -mb-px ${tab === k ? "border-[#E60000] text-[#E60000]" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{t.label}</button>)}</div>}
      <div className="flex flex-wrap gap-2 mb-3 items-center">
        <input data-testid="masters-search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder={`Search ${spec.label.toLowerCase()}…`} className={inputCls + " w-64"} />
        <div className="ml-auto flex gap-2">
          <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => imp(e.target.files[0])} data-testid="masters-import-input" />
          <button data-testid="masters-import-btn" onClick={() => fileRef.current.click()} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><UploadIcon className="h-3.5 w-3.5" />Import</button>
          <button data-testid="masters-export-btn" onClick={() => downloadFile(`/masters/${tab}/export/file`, `${tab}.xlsx`, { fmt: "xlsx" })} className="h-9 px-3 rounded-md border text-xs font-medium hover:bg-slate-50 flex items-center gap-1"><Download className="h-3.5 w-3.5" />Export</button>
          <button data-testid="masters-add-item-btn" onClick={() => setEdit({})} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Plus className="h-3.5 w-3.5" />Add</button>
        </div>
      </div>
      <DataTable testId={`masters-${tab}`} dense columns={cols} rows={data?.items} loading={!data} page={page} pages={data?.pages} total={data?.total} onPage={setPage} />
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-lg" data-testid="master-form-dialog"><DialogHeader><DialogTitle>{edit?.id ? "Edit" : "Add"} {spec.label}</DialogTitle></DialogHeader>
          {edit && <div className="grid grid-cols-2 gap-3">{spec.fields.map((k) => <Field key={k} label={k.replace(/_/g, " ")} className={["description", "params", "name"].includes(k) ? "col-span-2" : ""}>{input(k)}</Field>)}</div>}
          <div className="flex justify-end gap-2 mt-2"><button onClick={() => setEdit(null)} className="h-9 px-3 rounded-md border text-xs">Cancel</button><button data-testid="master-form-save" onClick={save} className="h-9 px-4 rounded-md btn-red text-xs font-semibold">Save</button></div>
        </DialogContent>
      </Dialog>
      <Dialog open={!!versions} onOpenChange={(o) => !o && setVersions(null)}>
        <DialogContent className="max-w-lg" data-testid="master-versions-dialog"><DialogHeader><DialogTitle>Version history · {versions?.item?.code || versions?.item?.alias || versions?.item?.city}</DialogTitle></DialogHeader>
          <div className="text-xs space-y-2 max-h-80 overflow-auto">{versions?.list.length === 0 && <div className="text-slate-400">No prior versions — this is v{versions?.item.version || 1}.</div>}{versions?.list.map((v) => <div key={v.id} className="border rounded p-2"><div className="font-semibold">v{v.version} · replaced {fmtDate(v.replaced_at)} by {v.by}</div><pre className="font-mono text-[10px] text-slate-500 mt-1 whitespace-pre-wrap">{JSON.stringify(v.snapshot, null, 0).slice(0, 400)}</pre></div>)}</div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
