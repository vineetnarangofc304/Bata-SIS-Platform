import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";
import { Loader2 } from "lucide-react";

const HERO = "https://images.unsplash.com/photo-1633464129147-777bdcc97c1d?crop=entropy&cs=srgb&fm=jpg&q=85&w=1400";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { await login(username, password); nav("/"); } catch (ex) { setErr(errMsg(ex)); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden lg:block bg-[#111827] overflow-hidden">
        <img src={HERO} alt="Bata retail store" className="absolute inset-0 h-full w-full object-cover opacity-40" />
        <div className="absolute inset-0 bg-gradient-to-t from-[#111827] via-[#111827]/60 to-transparent" />
        <div className="relative z-10 h-full flex flex-col justify-between p-12">
          <div className="flex items-center gap-3"><div className="h-10 w-10 rounded bg-[#E60000] flex items-center justify-center font-display font-bold text-white text-xl">B</div><span className="font-display text-white font-semibold text-lg">Bata SIS Sales Intelligence</span></div>
          <div className="max-w-lg">
            <h1 className="font-display text-4xl sm:text-5xl font-bold text-white leading-tight">Every partner file. Standardised. Validated. Trusted.</h1>
            <p className="mt-4 text-slate-300 text-base">Deterministic recognition of 9 SIS partner formats, human-approved corrections, full traceability from report back to source row.</p>
            <div className="mt-8 grid grid-cols-3 gap-4">
              {[["9", "SIS partners"], ["12", "reports"], ["100%", "audit coverage"]].map(([v, l]) => <div key={l} className="border-l-2 border-[#E60000] pl-3"><div className="font-display text-2xl font-bold text-white">{v}</div><div className="text-xs text-slate-400 uppercase tracking-wider">{l}</div></div>)}
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8 bg-white">
        <form onSubmit={submit} className="w-full max-w-sm fade-up" data-testid="login-form">
          <div className="h-1 w-12 bg-[#E60000] mb-6" />
          <h2 className="font-display text-2xl font-bold text-slate-900">Sign in</h2>
          <p className="text-sm text-slate-500 mt-1">Use your Bata SIS platform credentials.</p>
          <div className="mt-8 space-y-4">
            <label className="block"><span className="label-caps">Username or email</span>
              <input data-testid="login-username-input" value={username} onChange={(e) => setU(e.target.value)} autoFocus className="mt-1 w-full h-11 rounded-md border border-slate-300 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#E60000]/30 focus:border-[#E60000]" placeholder="admin" /></label>
            <label className="block"><span className="label-caps">Password</span>
              <input data-testid="login-password-input" type="password" value={password} onChange={(e) => setP(e.target.value)} className="mt-1 w-full h-11 rounded-md border border-slate-300 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#E60000]/30 focus:border-[#E60000]" placeholder="••••••••" /></label>
            {err && <div data-testid="login-error" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{err}</div>}
            <button data-testid="login-submit-button" disabled={busy} className="w-full h-11 rounded-md btn-red font-semibold text-sm flex items-center justify-center gap-2 disabled:opacity-60">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Sign in</button>
          </div>
          <div className="mt-8 text-xs text-slate-500 border border-slate-200 rounded-md p-3 bg-slate-50" data-testid="demo-accounts">
            <div className="label-caps mb-1.5">Demo accounts</div>
            <div className="grid grid-cols-3 gap-2 font-mono">
              <button type="button" onClick={() => { setU("admin"); setP("Admin@123"); }} className="hover:text-[#E60000] text-left">admin / Admin@123</button>
              <button type="button" onClick={() => { setU("ops"); setP("Ops@123"); }} className="hover:text-[#E60000] text-left">ops / Ops@123</button>
              <button type="button" onClick={() => { setU("mgmt"); setP("Mgmt@123"); }} className="hover:text-[#E60000] text-left">mgmt / Mgmt@123</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
