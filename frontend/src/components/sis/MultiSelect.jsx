import { useState } from "react";
import { ChevronDown, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function MultiSelect({ label, options = [], value = [], onChange, testId, width = "w-40" }) {
  const [q, setQ] = useState("");
  const opts = options.filter((o) => String(o).toLowerCase().includes(q.toLowerCase()));
  const toggle = (o) => onChange(value.includes(o) ? value.filter((v) => v !== o) : [...value, o]);
  const active = value.length > 0;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button data-testid={testId} className={`h-9 ${width} px-2.5 rounded-md border text-xs flex items-center justify-between gap-1 bg-white hover:bg-slate-50 ${active ? "border-[#E60000] text-slate-900" : "border-slate-300 text-slate-600"}`}>
          <span className="truncate"><span className="label-caps text-[10px] mr-1">{label}</span>{active ? (value.length === 1 ? value[0] : `${value.length} selected`) : "All"}</span>
          {active ? <X className="h-3 w-3 shrink-0 text-[#E60000]" onClick={(e) => { e.stopPropagation(); onChange([]); }} /> : <ChevronDown className="h-3 w-3 shrink-0" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-2 text-xs" data-testid={testId ? `${testId}-panel` : undefined}>
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${label.toLowerCase()}…`} className="w-full h-8 rounded border border-slate-300 px-2 mb-2 focus:outline-none focus:border-[#E60000]" />
        <div className="flex justify-between px-1 mb-1 text-[11px]"><button onClick={() => onChange(opts)} className="text-[#E60000] hover:underline">Select all</button><button onClick={() => onChange([])} className="text-slate-500 hover:underline">Clear</button></div>
        <div className="max-h-64 overflow-y-auto">
          {opts.map((o) => <label key={o} className="flex items-center gap-2 px-1.5 py-1 rounded hover:bg-slate-50 cursor-pointer"><input type="checkbox" checked={value.includes(o)} onChange={() => toggle(o)} className="accent-[#E60000]" /><span className="truncate">{String(o)}</span></label>)}
          {opts.length === 0 && <div className="text-slate-400 px-1.5 py-2">No options</div>}
        </div>
      </PopoverContent>
    </Popover>
  );
}
