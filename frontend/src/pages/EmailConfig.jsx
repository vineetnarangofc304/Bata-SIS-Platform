import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, ShieldCheck } from "lucide-react";
import api, { errMsg } from "@/lib/api";
import { PageHeader, Field, inputCls, selectCls } from "@/components/common/DataTable";
import { StatusBadge } from "@/components/common/Badges";
import Masters from "@/pages/Masters";

export default function EmailConfig() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({ provider: "imap", host: "", port: "993", mailbox: "sis-reports@bata.com", folder: "INBOX", poll_minutes: 15, credentials: { username: "", password: "", client_id: "", client_secret: "", tenant_id: "" } });
  const load = () => api.get("/email-config").then((r) => { setCfg(r.data); const c = r.data.connectors[0]; if (c) setForm((f) => ({ ...f, ...c, credentials: f.credentials })); });
  useEffect(() => { load(); }, []);
  const save = async () => { try { await api.put("/email-config/connector", form); toast.success("Connector configuration saved (credentials encrypted at rest)"); load(); } catch (e) { toast.error(errMsg(e)); } };
  const graph = form.provider === "graph";
  return (
    <div data-testid="email-config-page">
      <PageHeader title="Email Configuration" sub="Phase 2 — mailbox ingestion connector. Interface is built; activation awaits credentials. Nothing here is simulated." />
      <div className="card p-4 mb-5 flex items-start gap-3 border-amber-200 bg-amber-50/50" data-testid="email-status-banner"><Mail className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" /><div className="text-sm"><div className="font-semibold text-amber-900 flex items-center gap-2">Email ingestion <StatusBadge status={cfg?.connectors?.[0]?.status || "awaiting_credentials"} /></div><div className="text-xs text-amber-800 mt-1">{cfg?.note}</div></div></div>
      <div className="grid lg:grid-cols-2 gap-5 mb-6">
        <div className="card p-5 space-y-4" data-testid="email-connector-form">
          <h3 className="font-display font-semibold">Mailbox connector</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Provider"><select data-testid="email-provider-select" value={form.provider} onChange={(e) => setForm({ ...form, provider: e.target.value })} className={selectCls}><option value="graph">Microsoft Graph (Office 365)</option><option value="gmail">Gmail API</option><option value="imap">IMAP</option></select></Field>
            <Field label="Mailbox"><input data-testid="email-mailbox-input" value={form.mailbox || ""} onChange={(e) => setForm({ ...form, mailbox: e.target.value })} className={inputCls} /></Field>
            {form.provider === "imap" && <><Field label="IMAP host"><input value={form.host || ""} onChange={(e) => setForm({ ...form, host: e.target.value })} className={inputCls} placeholder="imap.office365.com" /></Field><Field label="Port"><input value={form.port || ""} onChange={(e) => setForm({ ...form, port: e.target.value })} className={inputCls} /></Field></>}
            <Field label="Folder"><input value={form.folder || ""} onChange={(e) => setForm({ ...form, folder: e.target.value })} className={inputCls} /></Field>
            <Field label="Poll interval (min)"><input type="number" value={form.poll_minutes || ""} onChange={(e) => setForm({ ...form, poll_minutes: Number(e.target.value) })} className={inputCls} /></Field>
          </div>
          <div className="border-t pt-3"><div className="label-caps mb-2 flex items-center gap-1"><ShieldCheck className="h-3 w-3" />Credentials — encrypted, never returned to the browser</div>
            <div className="grid grid-cols-2 gap-3">
              {graph ? <><Field label="Tenant ID"><input data-testid="email-cred-tenant" value={form.credentials.tenant_id} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, tenant_id: e.target.value } })} className={inputCls} /></Field><Field label="Client ID"><input value={form.credentials.client_id} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, client_id: e.target.value } })} className={inputCls} /></Field><Field label="Client secret"><input type="password" value={form.credentials.client_secret} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, client_secret: e.target.value } })} className={inputCls} /></Field></>
                : <><Field label="Username"><input data-testid="email-cred-username" value={form.credentials.username} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, username: e.target.value } })} className={inputCls} /></Field><Field label={form.provider === "gmail" ? "OAuth refresh token / app password" : "Password"}><input type="password" data-testid="email-cred-password" value={form.credentials.password} onChange={(e) => setForm({ ...form, credentials: { ...form.credentials, password: e.target.value } })} className={inputCls} /></Field></>}
            </div></div>
          <button data-testid="email-save-btn" onClick={save} className="h-9 px-4 rounded-md btn-red text-xs font-semibold">Save connector</button>
        </div>
        <div className="card p-5 text-sm" data-testid="email-flow">
          <h3 className="font-display font-semibold mb-3">How email ingestion will route files</h3>
          <ol className="list-decimal pl-5 space-y-2 text-slate-600 text-xs">
            <li>Connector polls the mailbox; each attachment (.xlsx/.xls/.csv) becomes a candidate.</li><li>Partner detected by <b>sender domain → sender email → subject pattern → attachment name → content</b> using the sender rules below.</li><li>Duplicate emails/attachments blocked by message-id + file hash.</li><li>File enters the same pipeline as manual upload: recognition → confidence → validation → review queue.</li><li>Unmatched senders land in the Review Queue as "partner unidentified".</li>
          </ol>
          <div className="mt-4 text-xs text-slate-500 border-t pt-3">Service interface: <code>services/pipeline.create_batch(data, filename, user, partner_code, source="email")</code> — already used by manual uploads, so no redesign is needed when credentials arrive.</div>
        </div>
      </div>
      <h3 className="font-display font-semibold mb-2">Sender rules</h3>
      <Masters fixedTab="sender_rules" />
    </div>
  );
}
