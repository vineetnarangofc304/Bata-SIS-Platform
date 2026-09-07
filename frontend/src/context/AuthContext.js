import { createContext, useContext, useEffect, useState, useCallback } from "react";
import api from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("bata_token");
    if (!t) return setLoading(false);
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const { data } = await api.post("/auth/login", { username, password });
    localStorage.setItem("bata_token", data.token);
    setUser({ ...data.user, role_label: data.role_label });
    return data;
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch (e) { /* ignore */ }
    localStorage.removeItem("bata_token");
    setUser(null);
  }, []);

  const can = useCallback((...roles) => !!user && roles.includes(user.role), [user]);
  return <AuthCtx.Provider value={{ user, loading, login, logout, can, isAdmin: user?.role === "admin", isOps: user?.role === "ops" || user?.role === "admin" }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
