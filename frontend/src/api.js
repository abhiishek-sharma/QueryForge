const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = {
  async query(file, question, maxRows = 100) {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("question", question);
    formData.append("max_rows", String(maxRows));

    const response = await fetch(`${API_BASE_URL}/api/v1/sql/query`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || "Request failed");
    }
    return response.json();
  },

  async generateSQL(question, schema) {
    const response = await fetch(`${API_BASE_URL}/api/v1/sql/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, schema }),
    });
    if (!response.ok) throw new Error("Failed to generate SQL");
    return response.json();
  },

  async extractSchema(file) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/api/v1/sql/extract-schema`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Failed to extract schema" }));
      throw new Error(err.detail || "Failed to extract schema");
    }
    return response.json();
  },

  async health() {
    const response = await fetch(`${API_BASE_URL}/api/v1/sql/health`);
    if (!response.ok) throw new Error("Health check failed");
    return response.json();
  },
};
