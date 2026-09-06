const BASE = "/api";

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  async analyze(file, sessionId) {
    const form = new FormData();
    form.append("file", file);
    if (sessionId) form.append("session_id", sessionId);
    const res = await fetch(`${BASE}/analyze`, { method: "POST", body: form });
    return handle(res);
  },

  async getSession(sessionId) {
    const res = await fetch(`${BASE}/session/${sessionId}`);
    return handle(res);
  },

  async resetSession(sessionId) {
    const res = await fetch(`${BASE}/session/${sessionId}/reset`, { method: "POST" });
    return handle(res);
  },

  async chat(sessionId, question) {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("question", question);
    const res = await fetch(`${BASE}/chat`, { method: "POST", body: form });
    return handle(res);
  },

  async exportPdf(sessionId) {
    const form = new FormData();
    form.append("session_id", sessionId);
    const res = await fetch(`${BASE}/export/pdf`, { method: "POST", body: form });
    if (!res.ok) throw new Error("PDF export failed");
    return res.blob();
  },

  csvUrl(sessionId) {
    return `${BASE}/export/csv/${sessionId}`;
  },
};
