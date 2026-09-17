import { useCallback, useRef, useState } from "react";
import { API } from "@/lib/api";

export function useAskStream() {
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef(null);

  const send = useCallback(async (sessionId, text, handlers) => {
    setStreaming(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const res = await fetch(`${API}/ask/sessions/${sessionId}/messages`, {
        method: "POST", signal: ctrl.signal, credentials: "include",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("bata_token") || ""}` },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${res.status}`); }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const p of parts) {
          const line = p.split("\n").find((l) => l.startsWith("data: "));
          if (line) handlers.onEvent(JSON.parse(line.slice(6)));
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") handlers.onEvent({ type: "error", message: e.message });
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, []);

  const stop = () => abortRef.current?.abort();
  return { send, stop, streaming };
}
