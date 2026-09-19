import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const api = axios.create({ baseURL: API });

api.interceptors.request.use((c) => {
  const t = localStorage.getItem("bata_token");
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});
api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !e.config?.url?.includes("/auth/login")) {
      localStorage.removeItem("bata_token");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(e);
  }
);

export const isGatewayError = (e) => !e?.response || [502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527].includes(e.response.status) || (typeof e.response.data === "string" && /cloudflare|<html/i.test(e.response.data));

export function errMsg(e) {
  if (isGatewayError(e)) return "The server is waking up or briefly unavailable — please try again in a few seconds.";
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Something went wrong";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" ");
  return d?.msg || String(d);
}

export async function downloadFile(path, filename, params) {
  const r = await api.get(path, { responseType: "blob", params });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default api;
