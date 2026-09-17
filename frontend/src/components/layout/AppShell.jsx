import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { LayoutDashboard, UploadCloud, Layers, CheckSquare, BarChart3, Sparkles, ShieldCheck, Database, Store, Mail, Users, FileText, Sliders, Bell, LogOut, MessageCircleQuestion, BookOpen } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import api from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { StatusBadge } from "@/components/common/Badges";
import { AskFab } from "@/components/ask/AskFab";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["admin", "ops", "management"] },
  { to: "/ask", label: "Ask Bata", icon: MessageCircleQuestion, roles: ["admin", "ops", "management"] },
  { to: "/upload", label: "Upload Data", icon: UploadCloud, roles: ["admin", "ops"] },
  { to: "/batches", label: "Ingestion Batches", icon: Layers, roles: ["admin", "ops", "management"] },
  { to: "/review", label: "Review Queue", icon: CheckSquare, roles: ["admin", "ops"], badge: "review" },
  { to: "/reports", label: "Sales Reports", icon: BarChart3, roles: ["admin", "ops", "management"] },
  { to: "/insights", label: "Insights", icon: Sparkles, roles: ["admin", "ops", "management"] },
  { to: "/data-quality", label: "Data Quality", icon: ShieldCheck, roles: ["admin", "ops", "management"] },
  { to: "/masters", label: "Masters", icon: Database, roles: ["admin"] },
  { to: "/partners", label: "Partner Configuration", icon: Store, roles: ["admin"] },
  { to: "/email-config", label: "Email Configuration", icon: Mail, roles: ["admin"] },
  { to: "/users", label: "Users & Roles", icon: Users, roles: ["admin"] },
  { to: "/audit", label: "Audit Logs", icon: FileText, roles: ["admin", "ops", "management"] },
  { to: "/settings", label: "Settings", icon: Sliders, roles: ["admin"] },
  { to: "/help", label: "Help Center", icon: BookOpen, roles: ["admin", "ops", "management"] },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [summary, setSummary] = useState(null);
  const [notes, setNotes] = useState({ items: [], unread: 0 });

  const load = () => {
    api.get("/batches/summary").then((r) => setSummary(r.data)).catch(() => {});
    api.get("/notifications", { params: { limit: 15 } }).then((r) => setNotes(r.data)).catch(() => {});
  };
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, []);

  const markAll = async () => { await api.post("/notifications/read", {}); load(); };

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 bg-[#111827] text-slate-300 flex flex-col fixed inset-y-0 left-0 z-20" data-testid="sidebar">
        <div className="h-1 bg-[#E60000]" />
        <div className="px-5 py-5 flex items-center gap-3 border-b border-white/5">
          <img src="/bata-logo-white.svg" alt="Bata" className="h-6 w-auto" data-testid="sidebar-logo" />
          <div className="border-l border-white/15 pl-3"><div className="font-display font-semibold text-white leading-tight text-sm">SIS</div><div className="text-[10px] uppercase tracking-widest text-slate-500">Sales Intelligence</div></div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV.filter((n) => n.roles.includes(user.role)).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"} data-testid={`nav-${n.label.toLowerCase().replace(/[^a-z]+/g, "-")}`} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
              <n.icon className="h-4 w-4" /><span className="flex-1">{n.label}</span>
              {n.badge === "review" && summary?.awaiting_review > 0 && <span className="chip bg-white/15 text-white" data-testid="nav-review-badge">{summary.awaiting_review}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-white/5 text-xs">
          <div className="text-white font-medium">{user.name}</div>
          <div className="text-slate-500">{user.role_label}</div>
        </div>
      </aside>
      <div className="flex-1 ml-60 flex flex-col min-w-0">
        <header className="h-14 sticky top-0 z-10 bg-white border-b border-slate-200 flex items-center px-6 gap-4" data-testid="topbar">
          <div className="flex items-center gap-3 text-xs text-slate-500 flex-1">
            {summary && (
              <>
                <span className="chip bg-slate-100 text-slate-700" data-testid="ticker-total">{summary.total_batches} batches</span>
                {summary.processing > 0 && <span className="chip bg-blue-50 text-blue-700"><span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />{summary.processing} processing</span>}
                {summary.awaiting_review > 0 && <button onClick={() => nav("/review")} className="chip bg-amber-50 text-amber-700 hover:bg-amber-100" data-testid="ticker-review">{summary.awaiting_review} awaiting review</button>}
                {summary.open_exceptions > 0 && <button onClick={() => nav("/review")} className="chip bg-red-50 text-red-700 hover:bg-red-100" data-testid="ticker-exceptions">{summary.open_exceptions} open exceptions</button>}
              </>
            )}
          </div>
          <Popover>
            <PopoverTrigger asChild>
              <button className="relative p-2 rounded-md hover:bg-slate-100" data-testid="notifications-bell">
                <Bell className="h-4 w-4 text-slate-600" />
                {notes.unread > 0 && <span className="absolute -top-0.5 -right-0.5 h-4 min-w-4 px-1 rounded-full bg-[#E60000] text-white text-[10px] font-bold flex items-center justify-center" data-testid="notifications-unread">{notes.unread}</span>}
              </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-96 p-0" data-testid="notifications-panel">
              <div className="flex items-center justify-between px-4 py-2.5 border-b"><span className="font-semibold text-sm">Notifications</span><button onClick={markAll} className="text-xs text-[#E60000] hover:underline" data-testid="notifications-mark-read">Mark all read</button></div>
              <div className="max-h-96 overflow-y-auto divide-y">
                {notes.items.length === 0 && <div className="p-6 text-center text-xs text-slate-400">No notifications</div>}
                {notes.items.map((n) => (
                  <button key={n.id} onClick={() => n.link && nav(n.link)} className={`w-full text-left px-4 py-2.5 hover:bg-slate-50 ${n.read ? "opacity-60" : ""}`} data-testid="notification-item">
                    <div className="flex items-center justify-between gap-2"><span className="text-[13px] font-medium text-slate-800">{n.title}</span><StatusBadge status={n.severity} /></div>
                    <div className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</div>
                    <div className="text-[10px] text-slate-400 mt-1">{timeAgo(n.created_at)} · in-app {n.channels?.email === "inactive" ? "· email/WhatsApp inactive" : ""}</div>
                  </button>
                ))}
              </div>
            </PopoverContent>
          </Popover>
          <div className="h-8 w-8 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-bold" title={user.email}>{user.name?.[0]}</div>
          <button onClick={async () => { await logout(); nav("/login"); }} className="p-2 rounded-md hover:bg-slate-100" title="Sign out" data-testid="logout-btn"><LogOut className="h-4 w-4 text-slate-600" /></button>
        </header>
        <main className="p-6 sm:p-8 flex-1"><Outlet context={{ refreshShell: load }} /></main>
      </div>
      <AskFab />
    </div>
  );
}
