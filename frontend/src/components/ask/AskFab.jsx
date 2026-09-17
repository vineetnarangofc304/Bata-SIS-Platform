import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { MessageCircleQuestion, Maximize2, X } from "lucide-react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ChatPanel } from "./ChatPanel";

export function AskFab() {
  const [open, setOpen] = useState(false);
  const [sid, setSid] = useState(null);
  const nav = useNavigate();
  const { pathname } = useLocation();
  if (pathname.startsWith("/ask")) return null;
  return (
    <>
      <button data-testid="ask-fab" onClick={() => setOpen(true)} title="Ask Bata" className="fixed bottom-6 right-6 z-30 h-12 pl-4 pr-5 rounded-full bg-[#E60000] text-white shadow-lg shadow-red-600/30 flex items-center gap-2 text-sm font-semibold hover:bg-[#c50000] hover:-translate-y-0.5 transition-all">
        <MessageCircleQuestion className="h-5 w-5" />Ask Bata
      </button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="w-full sm:max-w-xl p-0 flex flex-col [&>button]:hidden" data-testid="ask-drawer">
          <div className="flex items-center justify-between px-4 h-12 border-b border-slate-200">
            <SheetTitle className="text-sm font-display font-semibold flex items-center gap-2"><span className="h-5 w-5 rounded-full bg-[#E60000] text-white text-[10px] font-bold flex items-center justify-center">B</span>Ask Bata</SheetTitle>
            <div className="flex items-center gap-1">
              <button data-testid="ask-drawer-expand" title="Open full page" onClick={() => { setOpen(false); nav(sid ? `/ask?session=${sid}` : "/ask"); }} className="p-1.5 rounded hover:bg-slate-100"><Maximize2 className="h-4 w-4 text-slate-500" /></button>
              <button data-testid="ask-drawer-close" onClick={() => setOpen(false)} className="p-1.5 rounded hover:bg-slate-100"><X className="h-4 w-4 text-slate-500" /></button>
            </div>
          </div>
          <div className="flex-1 min-h-0 px-4 pb-3 flex flex-col"><ChatPanel sessionId={sid} onSessionReady={(s) => setSid(s.id)} compact /></div>
        </SheetContent>
      </Sheet>
    </>
  );
}
