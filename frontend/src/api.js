// Same-origin by default: the Vite dev server proxies /api to the backend on :8000.
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

async function errorMessage(response) {
  const body = await response.json().catch(() => null);
  if (body && typeof body.detail === "string") return body.detail;
  if (response.status === 413) return "File is too large";
  return `Request failed (${response.status})`;
}

export const api = {
  async query(file, question, maxRows = 100) {
    const form = new FormData();
    form.append("file", file);
    form.append("question", question);
    form.append("max_rows", String(maxRows));
    let response;
    try {
      response = await fetch(`${API_BASE_URL}/api/v1/sql/query`, { method: "POST", body: form });
    } catch {
      throw new Error("Cannot reach the QueryForge backend. Is it running on port 8000?");
    }
    if (!response.ok) throw new Error(await errorMessage(response));
    return response.json();
  },

  async health() {
    const response = await fetch(`${API_BASE_URL}/api/v1/sql/health`);
    if (!response.ok) throw new Error("Health check failed");
    return response.json();
  },
};
