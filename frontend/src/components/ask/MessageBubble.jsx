import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, ChevronRight, Database, Loader2, AlertCircle } from "lucide-react";
import { brand } from "@/lib/brand";

const fmtCell = (v) => v === null || v === undefined ? "—" : typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : typeof v === "object" ? JSON.stringify(v) : String(v);

function ToolChip({ t }) {
  const [open, setOpen] = useState(false);
  const cols = t.rows?.length ? Object.keys(t.rows[0]).filter((k) => typeof t.rows[0][k] !== "object" || t.rows[0][k] === null).slice(0, 9) : [];
  return (
    <div className="border border-slate-200 rounded-md bg-white text-xs" data-testid="ask-tool-chip">
      <button onClick={() => setOpen((o) => !o)} className="w-full flex items-center gap-2 px-2.5 py-1.5 text-left hover:bg-slate-50">
        {t.pending ? <Loader2 className="h-3 w-3 animate-spin text-[#E60000]" /> : <Database className="h-3 w-3 text-slate-400" />}
        <span className="font-mono text-slate-700">{t.name}</span>
        {t.args && Object.keys(t.args).length > 0 && <span className="text-slate-400 truncate flex-1">{JSON.stringify(t.args)}</span>}
        {t.row_count !== undefined && t.row_count !== null && <span className="chip bg-slate-100 text-slate-600">{t.row_count} rows</span>}
        {t.error && <span className="chip bg-red-50 text-red-600">error</span>}
        {cols.length > 0 && (open ? <ChevronDown className="h-3 w-3 text-slate-400" /> : <ChevronRight className="h-3 w-3 text-slate-400" />)}
      </button>
      {open && cols.length > 0 && (
        <div className="overflow-x-auto border-t border-slate-100"><table className="data-table w-full text-[11px]"><thead><tr>{cols.map((c) => <th key={c}>{c.replace(/_/g, " ")}</th>)}</tr></thead>
          <tbody>{t.rows.map((r, i) => <tr key={i}>{cols.map((c) => <td key={c} className={typeof r[c] === "number" ? "text-right tabular" : ""}>{fmtCell(r[c])}</td>)}</tr>)}</tbody></table></div>
      )}
    </div>
  );
}

export function MessageBubble({ m }) {
  if (m.role === "user") {
    return <div className="flex justify-end" data-testid="ask-user-message"><div className="max-w-[80%] bg-[#111827] text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm whitespace-pre-wrap">{m.content}</div></div>;
  }
  return (
    <div className="flex gap-3" data-testid="ask-assistant-message">
      <div className="h-7 w-7 rounded-full bg-[#E60000] text-white text-[10px] font-bold flex items-center justify-center shrink-0 mt-1">{brand.name[0]}</div>
      <div className="flex-1 min-w-0 space-y-2">
        {m.tools?.length > 0 && <div className="space-y-1" data-testid="ask-tools-used">{m.tools.map((t, i) => <ToolChip key={i} t={t} />)}</div>}
        {m.content ? <div className="prose-chat text-sm text-slate-800"><ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown></div>
          : m.pending ? <div className="text-xs text-slate-400 flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" />{m.tools?.some((t) => t.pending) ? "Querying live data…" : "Thinking…"}</div> : null}
        {m.error && <div className="text-xs text-red-600 flex items-center gap-1.5" data-testid="ask-error"><AlertCircle className="h-3.5 w-3.5" />{m.error}</div>}
      </div>
    </div>
  );
}
