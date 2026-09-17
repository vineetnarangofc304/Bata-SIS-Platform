import { useEffect, useRef, useState } from "react";
import { Send, Square, Sparkles } from "lucide-react";
import api from "@/lib/api";
import { useAskStream } from "./useAskStream";
import { MessageBubble } from "./MessageBubble";

export function ChatPanel({ sessionId, onSessionReady, onFirstMessage, compact }) {
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const { send, stop, streaming } = useAskStream();
  const endRef = useRef(null);
  const sidRef = useRef(sessionId);
  const createdRef = useRef(null);

  useEffect(() => { api.get("/ask/suggestions").then((r) => setSuggestions(r.data)).catch(() => {}); }, []);
  useEffect(() => {
    if (sessionId && sessionId === createdRef.current) { sidRef.current = sessionId; return; }
    sidRef.current = sessionId;
    if (!sessionId) { setMsgs([]); return; }
    api.get(`/ask/sessions/${sessionId}`).then((r) => setMsgs(r.data.messages)).catch(() => setMsgs([]));
  }, [sessionId]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const ask = async (q) => {
    const question = (q ?? text).trim();
    if (!question || streaming) return;
    setText("");
    let sid = sidRef.current;
    if (!sid) { const r = await api.post("/ask/sessions"); sid = r.data.id; sidRef.current = sid; createdRef.current = sid; onSessionReady?.(r.data); }
    const isFirst = msgs.length === 0;
    setMsgs((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "", tools: [], pending: true }]);
    const patch = (fn) => setMsgs((m) => { const c = [...m]; c[c.length - 1] = fn(c[c.length - 1]); return c; });
    await send(sid, question, { onEvent: (ev) => {
      if (ev.type === "delta") patch((a) => ({ ...a, content: a.content + ev.content }));
      else if (ev.type === "tool_call") patch((a) => ({ ...a, tools: [...a.tools, { name: ev.name, args: ev.args, pending: true }] }));
      else if (ev.type === "tool_result") patch((a) => { const tools = [...a.tools]; const i = tools.map((t) => t.pending).lastIndexOf(true); const merged = { ...ev, pending: false }; delete merged.type; if (i >= 0) tools[i] = { ...tools[i], ...merged }; else tools.push(merged); return { ...a, tools }; });
      else if (ev.type === "error") patch((a) => ({ ...a, error: ev.message, pending: false }));
      else if (ev.type === "done") { patch((a) => ({ ...a, pending: false })); if (isFirst) onFirstMessage?.(sid, question); }
    } });
    patch((a) => ({ ...a, pending: false }));
  };

  return (
    <div className="flex flex-col h-full min-h-0" data-testid="ask-chat-panel">
      <div className="flex-1 overflow-y-auto px-1 py-2 space-y-5">
        {msgs.length === 0 && (
          <div className={`${compact ? "pt-4" : "pt-10"} max-w-2xl mx-auto text-center`} data-testid="ask-empty-state">
            <div className="mx-auto h-12 w-12 rounded-2xl bg-[#E60000]/10 flex items-center justify-center"><Sparkles className="h-6 w-6 text-[#E60000]" /></div>
            <h2 className="font-display font-semibold text-lg mt-4 text-slate-900">Ask Bata anything about SIS sales</h2>
            <p className="text-sm text-slate-500 mt-1">Targets, stores, articles, stock cover, margins, data quality — answered from live data, with the queries shown.</p>
            <div className="grid sm:grid-cols-2 gap-2 mt-6 text-left">
              {suggestions.slice(0, compact ? 4 : 8).map((s) => <button key={s} data-testid="ask-suggestion" onClick={() => ask(s)} className="card card-hover px-3 py-2.5 text-[13px] text-slate-700 text-left hover:border-[#E60000]/40">{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => <MessageBubble key={m.id || i} m={m} />)}
        <div ref={endRef} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="border-t border-slate-200 pt-3 mt-2">
        <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 focus-within:ring-2 focus-within:ring-[#E60000]/30 focus-within:border-[#E60000]">
          <textarea data-testid="ask-input" value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }} rows={compact ? 1 : 2} placeholder="e.g. Which Lifestyle stores are below 80% of their Week 32 target?" className="flex-1 resize-none bg-transparent text-sm focus:outline-none max-h-40" />
          {streaming ? <button type="button" data-testid="ask-stop-btn" onClick={stop} className="h-9 w-9 rounded-lg bg-slate-900 text-white flex items-center justify-center"><Square className="h-3.5 w-3.5" /></button>
            : <button type="submit" data-testid="ask-send-btn" disabled={!text.trim()} className="h-9 w-9 rounded-lg btn-red flex items-center justify-center disabled:opacity-40"><Send className="h-4 w-4" /></button>}
        </div>
        <div className="text-[10px] text-slate-400 mt-1.5 px-1">GPT-5.4 · answers come only from live queries on the reporting data · read-only</div>
      </form>
    </div>
  );
}
