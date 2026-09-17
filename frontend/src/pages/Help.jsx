import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Search, BookOpen, Sigma } from "lucide-react";
import api from "@/lib/api";
import { PageHeader, inputCls } from "@/components/common/DataTable";

export default function Help() {
  const [help, setHelp] = useState(null);
  const [q, setQ] = useState("");
  const { hash } = useLocation();
  useEffect(() => { api.get("/ask/help").then((r) => setHelp(r.data)); }, []);
  useEffect(() => {
    if (!help || !hash) return;
    const el = document.getElementById(hash.slice(1));
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "start" }); el.classList.add("help-flash"); setTimeout(() => el.classList.remove("help-flash"), 2000); }
  }, [help, hash]);
  const sections = useMemo(() => {
    if (!help) return [];
    const w = q.trim().toLowerCase();
    if (!w) return help.sections;
    return help.sections.map((s) => ({ ...s, items: s.items.filter((i) => `${i.title} ${i.body} ${i.formula || ""}`.toLowerCase().includes(w)) })).filter((s) => s.items.length);
  }, [help, q]);
  if (!help) return <div className="text-slate-400 text-sm">Loading help…</div>;
  const count = sections.reduce((n, s) => n + s.items.length, 0);
  return (
    <div data-testid="help-page">
      <PageHeader title="Help Center" sub="Every dashboard KPI, report, formula, validation rule and screen — exactly as computed by the platform." actions={
        <div className="relative"><Search className="h-4 w-4 text-slate-400 absolute left-2.5 top-2.5" /><input data-testid="help-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search formulas, reports, rules…" className={inputCls + " pl-8 w-72"} /></div>} />
      <div className="grid lg:grid-cols-[220px_1fr] gap-6">
        <nav className="card p-2 self-start sticky top-20 hidden lg:block" data-testid="help-toc">
          {help.sections.map((s) => <a key={s.id} href={`#${s.id}`} className="block px-3 py-1.5 rounded text-[13px] text-slate-700 hover:bg-slate-100">{s.title}<span className="text-slate-400 text-xs"> · {s.items.length}</span></a>)}
        </nav>
        <div className="space-y-8 min-w-0">
          {q && <div className="text-xs text-slate-500" data-testid="help-search-count">{count} result{count === 1 ? "" : "s"} for “{q}”</div>}
          {sections.map((s) => (
            <section key={s.id} id={s.id} className="scroll-mt-20" data-testid={`help-section-${s.id}`}>
              <div className="flex items-center gap-2 mb-1"><BookOpen className="h-4 w-4 text-[#E60000]" /><h2 className="font-display font-semibold text-lg text-slate-900">{s.title}</h2></div>
              {s.intro && <div className="text-sm text-slate-600 mb-4 prose-chat"><ReactMarkdown remarkPlugins={[remarkGfm]}>{s.intro}</ReactMarkdown></div>}
              <div className="grid md:grid-cols-2 gap-3">
                {s.items.map((it) => (
                  <article key={it.id} id={it.id} className="card p-4 scroll-mt-20 transition-colors" data-testid={`help-item-${it.id}`}>
                    <h3 className="font-semibold text-sm text-slate-900">{it.title}</h3>
                    {it.formula && <div className="mt-2 flex items-start gap-2 rounded-md bg-slate-900 text-slate-100 px-3 py-2 font-mono text-xs"><Sigma className="h-3.5 w-3.5 mt-0.5 text-[#E60000] shrink-0" /><span>{it.formula}</span></div>}
                    <div className="text-[13px] text-slate-600 mt-2 prose-chat"><ReactMarkdown remarkPlugins={[remarkGfm]}>{it.body}</ReactMarkdown></div>
                  </article>
                ))}
              </div>
            </section>
          ))}
          {sections.length === 0 && <div className="card p-8 text-center text-slate-400 text-sm">No help topics match “{q}”. Try Ask Bata instead.</div>}
        </div>
      </div>
    </div>
  );
}
