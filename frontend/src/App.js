import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AppShell from "@/components/layout/AppShell";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Upload from "@/pages/Upload";
import Batches from "@/pages/Batches";
import BatchDetail from "@/pages/BatchDetail";
import ReviewQueue from "@/pages/ReviewQueue";
import Reports from "@/pages/Reports";
import Insights from "@/pages/Insights";
import DataQuality from "@/pages/DataQuality";
import Masters from "@/pages/Masters";
import PartnerConfig from "@/pages/PartnerConfig";
import EmailConfig from "@/pages/EmailConfig";
import UsersPage from "@/pages/Users";
import AuditLogs from "@/pages/AuditLogs";
import Settings from "@/pages/Settings";
import Ask from "@/pages/Ask";
import Help from "@/pages/Help";
import SisSales from "@/pages/SisSales";

function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-400 text-sm">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

const ADMIN = ["admin"];
const OPS = ["admin", "ops"];

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Protected><AppShell /></Protected>}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/upload" element={<Protected roles={OPS}><Upload /></Protected>} />
              <Route path="/batches" element={<Batches />} />
              <Route path="/batches/:id" element={<BatchDetail />} />
              <Route path="/review" element={<Protected roles={OPS}><ReviewQueue /></Protected>} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/sis-sales" element={<SisSales />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="/data-quality" element={<DataQuality />} />
              <Route path="/masters" element={<Protected roles={ADMIN}><Masters /></Protected>} />
              <Route path="/partners" element={<Protected roles={ADMIN}><PartnerConfig /></Protected>} />
              <Route path="/email-config" element={<Protected roles={ADMIN}><EmailConfig /></Protected>} />
              <Route path="/users" element={<Protected roles={ADMIN}><UsersPage /></Protected>} />
              <Route path="/audit" element={<AuditLogs />} />
              <Route path="/settings" element={<Protected roles={ADMIN}><Settings /></Protected>} />
              <Route path="/ask" element={<Ask />} />
              <Route path="/help" element={<Help />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
