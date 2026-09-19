import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, Trash2, MessageSquare } from "lucide-react";
import api from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { PageHeader } from "@/components/common/DataTable";
import { ChatPanel } from "@/components/ask/ChatPanel";
import { HelpLink } from "@/components/common/HelpLink";
import { brand } from "@/lib/brand";

export default function Ask() {
  const [sp, setSp] = useSearchParams();
  const [sessions, setSessions] = useState([]);
  const sid = sp.get("session") || null;
  const load = () => api.get("/ask/sessions").then((r) => setSessions(r.data));
  useEffect(() => { load(); }, []);
  const select = (id) => setSp(id ? { session: id } : {});
  const del = async (id) => { await api.delete(`/ask/sessions/${id}`); if (sid === id) select(null); load(); };
  return (
    <div data-testid="ask-page" className="flex flex-col h-[calc(100vh-7.5rem)]">
      <PageHeader title={<span className="flex items-center gap-2">Ask {brand.name} <HelpLink id="a-what" /></span>} sub="Conversational analytics agent over your live SIS data — every number comes from a query you can inspect." actions={
        <button data-testid="ask-new-session-btn" onClick={() => select(null)} className="h-9 px-3 rounded-md btn-red text-xs font-semibold flex items-center gap-1"><Plus className="h-3.5 w-3.5" />New conversation</button>} />
      <div className="grid lg:grid-cols-[240px_1fr] gap-5 flex-1 min-h-0">
        <div className="card p-2 overflow-y-auto" data-testid="ask-session-list">
          <div className="label-caps px-2 py-1">Conversations</div>
          {sessions.length === 0 && <div className="text-xs text-slate-400 px-2 py-3">No conversations yet.</div>}
          {sessions.map((s) => (
            <div key={s.id} className={`flex items-center group rounded ${sid === s.id ? "bg-[#E60000]/10" : "hover:bg-slate-100"}`}>
              <button data-testid="ask-session-item" onClick={() => select(s.id)} className="flex-1 text-left px-2.5 py-2 min-w-0">
                <div className="flex items-center gap-1.5 text-[13px] text-slate-800 truncate"><MessageSquare className="h-3 w-3 text-slate-400 shrink-0" /><span className="truncate">{s.title}</span></div>
                <div className="text-[10px] text-slate-400 pl-[18px]">{timeAgo(s.updated_at)}</div>
              </button>
              <button data-testid="ask-session-delete" onClick={() => del(s.id)} className="p-1.5 mr-1 opacity-0 group-hover:opacity-100"><Trash2 className="h-3 w-3 text-slate-400 hover:text-red-600" /></button>
            </div>
          ))}
        </div>
        <div className="card p-4 min-h-0 flex flex-col">
          <ChatPanel sessionId={sid} onSessionReady={(s) => { select(s.id); }} onFirstMessage={load} />
        </div>
      </div>
    </div>
  );
}
