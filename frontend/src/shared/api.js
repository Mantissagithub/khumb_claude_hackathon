// ─────────────────────────────────────────────────────────────
// FROZEN shared fetch helpers (PLAN.md §4.3). Do NOT change after 0:30.
// All calls go to /api/... — Vite proxies to FastAPI :8000.
// ─────────────────────────────────────────────────────────────
const J = (p, body) =>
  fetch(`/api/${p}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => r.json());

const F = (p, form) =>
  fetch(`/api/${p}`, { method: "POST", body: form }).then((r) => r.json());

export const faceSearch = (form) => F("face/search", form);
export const voiceMatch = (form) => F("voice/match", form);
export const runSim = (body) => J("sim/run", body);
export const bestRoute = (body) => J("routing/best", body);

// Simple health check used by the dashboard to show backend status.
export const ping = () =>
  fetch("/api/ping")
    .then((r) => (r.ok ? r.json() : Promise.reject(r)))
    .catch(() => null);
