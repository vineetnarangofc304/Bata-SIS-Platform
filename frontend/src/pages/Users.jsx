import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Plus, Pencil } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { DataTable, PageHeader, Field, inputCls, selectCls } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export default function UsersPage() {
  const [data, setData] = useState(null);
  const [roles, setRoles] = useState([]);
  const [edit, setEdit] = useState(null);
  const load = () => api.get("/users").then((r) => setData(r.data));
  useEffect(() => { load(); api.get("/users/roles").then((r) => setRoles(r.data)); }, []);
  const save = async () => { try { if (edit.id) await api.put(`/users/${edit.id}`, edit); else await api.post("/users", edit); toast.success("User saved"); setEdit(null); load(); } catch (e) { toast.error(errMsg(e)); } };
  const PERMS = { admin: "Users, partners, mappings, rules, masters, email config, exceptions — everything", ops: "Upload, review mappings, fix exceptions, approve/reject/reprocess, view history", management: "View dashboards & reports, filter, export. No edits." };
  return (
    <div data-testid="users-page">
      <PageHeader title="Users & Roles" sub="Username + password authentication with three roles. SSO can be layered on later." actions={<button data-testid="user-add-btn" onClick={() => setEdit({ username: "", email: "", name: "", role: "ops", password: "", active: true })} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Plus className="h-3.5 w-3.5" />Add user</button>} />
      <div className="grid md:grid-cols-3 gap-3 mb-5 stagger">{roles.map((r) => <div key={r.key} className="card p-4" data-testid={`role-card-${r.key}`}><div className="font-display font-semibold">{r.label}</div><div className="text-xs text-slate-500 mt-1">{PERMS[r.key]}</div></div>)}</div>
      <DataTable testId="users-table" columns={[
        { key: "username", label: "Username", render: (u) => <span className="font-mono font-semibold">{u.username}</span> }, { key: "name", label: "Name" }, { key: "email", label: "Email" },
        { key: "role", label: "Role", render: (u) => <StatusBadge status={roles.find((r) => r.key === u.role)?.label || u.role} /> }, { key: "active", label: "Status", render: (u) => <StatusBadge status={u.active ? "active" : "inactive"} /> },
        { key: "last_login", label: "Last login", render: (u) => <span className="text-xs text-slate-500">{u.last_login ? fmtDate(u.last_login) : "never"}</span> },
        { key: "act", label: "", render: (u) => <button data-testid="user-edit-btn" onClick={() => setEdit({ ...u, password: "" })} className="p-1 rounded hover:bg-slate-100"><Pencil className="h-3.5 w-3.5 text-slate-500" /></button> },
      ]} rows={data?.items} loading={!data} />
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}>
        <DialogContent className="max-w-md" data-testid="user-form-dialog"><DialogHeader><DialogTitle>{edit?.id ? "Edit user" : "Add user"}</DialogTitle></DialogHeader>
          {edit && <div className="grid grid-cols-2 gap-3">
            <Field label="Username"><input data-testid="user-form-username" disabled={!!edit.id} value={edit.username} onChange={(e) => setEdit({ ...edit, username: e.target.value })} className={inputCls} /></Field>
            <Field label="Full name"><input data-testid="user-form-name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} className={inputCls} /></Field>
            <Field label="Email" className="col-span-2"><input data-testid="user-form-email" value={edit.email} onChange={(e) => setEdit({ ...edit, email: e.target.value })} className={inputCls} /></Field>
            <Field label="Role"><select data-testid="user-form-role" value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value })} className={selectCls}>{roles.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}</select></Field>
            <Field label="Status"><select data-testid="user-form-active" value={String(edit.active)} onChange={(e) => setEdit({ ...edit, active: e.target.value === "true" })} className={selectCls}><option value="true">Active</option><option value="false">Deactivated</option></select></Field>
            <Field label={edit.id ? "New password (leave blank to keep)" : "Password (min 8 chars)"} className="col-span-2"><input data-testid="user-form-password" type="password" value={edit.password} onChange={(e) => setEdit({ ...edit, password: e.target.value })} className={inputCls} /></Field>
          </div>}
          <div className="flex justify-end gap-2 mt-2"><button onClick={() => setEdit(null)} className="h-9 px-3 rounded-md border text-xs">Cancel</button><button data-testid="user-form-save" onClick={save} className="h-9 px-4 rounded-md btn-red text-xs font-semibold">Save</button></div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
