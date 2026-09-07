export function inr(n, opts = {}) {
  if (n === null || n === undefined || isNaN(n)) return "—";
  const v = Number(n);
  if (opts.compact) {
    if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
    if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(2)} L`;
  }
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: opts.decimals ?? 0 }).format(v);
}
export const num = (n) => (n === null || n === undefined ? "—" : new Intl.NumberFormat("en-IN").format(n));
export const pct = (n, d = 1) => (n === null || n === undefined ? "—" : `${Number(n).toFixed(d)}%`);
export function fmtDate(s, withTime = true) {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return d.toLocaleString("en-IN", { day: "2-digit", month: "short", ...(withTime ? { hour: "2-digit", minute: "2-digit" } : { year: "numeric" }) });
}
export const shortId = (id) => (id ? id.slice(0, 8).toUpperCase() : "—");
export const timeAgo = (s) => {
  const diff = (Date.now() - new Date(s)) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
};
