// ─────────────────────────────────────────────────────────────
// Face-recognition client. Wraps the Python/FastAPI face-search
// service (backend/services/face_search) when VITE_FACE_API is set.
// Falls back to a local score→verdict mapping so the admin UI renders
// identically whether the live engine or the text-matcher produced a
// score. Contract mirrors backend/services/face_search/logic.py.
// ─────────────────────────────────────────────────────────────

export const FACE_API = import.meta.env.VITE_FACE_API?.replace(/\/$/, "") || null;
export const faceEngineLive = !!FACE_API;

// Verdict bands for facenet/ArcFace cosine on L2-normalised embeddings.
// Kept in sync with logic.py: STRONG 0.62 · LIKELY 0.45 · WEAK/POSSIBLE 0.32.
export const BANDS = { STRONG: 0.62, LIKELY: 0.45, POSSIBLE: 0.32 };

export function confidencePct(score) {
  const s = Number(score) || 0;
  return Math.round(Math.max(0, Math.min(1, (s - 0.2) / 0.6)) * 1000) / 10;
}

export function bandFor(score) {
  const s = Number(score) || 0;
  if (s >= BANDS.STRONG) return { band: "STRONG", label: "Match — very likely the same person", is_match: true };
  if (s >= BANDS.LIKELY) return { band: "LIKELY", label: "Likely the same person", is_match: true };
  if (s >= BANDS.POSSIBLE) return { band: "POSSIBLE", label: "Possible — needs human review", is_match: false };
  return { band: "NO_MATCH", label: "No match found", is_match: false };
}

// Build the same verdict object the FastAPI service returns, from a raw
// 0..1 score (used by the text-matcher fallback in the Alerts feed).
export function verdictFromScore(score, { second = null, reasonHint } = {}) {
  const b = bandFor(score);
  const reasons = [
    `Face/profile similarity ${Number(score).toFixed(2)} — ${b.band.toLowerCase().replace("_", " ")} similarity.`,
  ];
  if (second != null && score - second >= 0.12)
    reasons.push(`Clear margin (+${(score - second).toFixed(2)}) over the next-closest candidate.`);
  if (reasonHint) reasons.push(reasonHint);
  reasons.push("Decision support only — a trained operator must visually confirm before any reunification.");
  return {
    ...b,
    confidence_pct: confidencePct(score),
    score: Math.round(Number(score) * 1e4) / 1e4,
    reasons,
    source: "fallback",
  };
}

async function postForm(path, form) {
  const res = await fetch(`${FACE_API}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    let msg = `Face service error (${res.status})`;
    try { msg = (await res.json())?.detail || msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export async function faceHealth() {
  if (!FACE_API) return { status: "offline", note: "VITE_FACE_API not configured — using fallback matcher." };
  const res = await fetch(`${FACE_API}/api/face/health`);
  if (!res.ok) throw new Error(`Face service health ${res.status}`);
  return { ...(await res.json()), source: "live" };
}

// Is the person in `image` present in the supporting images? -> verdict
export async function faceVerify(image, support = [], consentGiven = true) {
  const fd = new FormData();
  fd.append("image", image);
  (Array.isArray(support) ? support : [support]).forEach((s) => fd.append("support", s));
  fd.append("consent_given", String(consentGiven));
  return postForm("/api/face/verify", fd);
}

// Search a query face against the authorized camera gallery -> matches + route
export async function faceSearch(image, { topK = 5, consentGiven = true } = {}) {
  const fd = new FormData();
  fd.append("image", image);
  fd.append("top_k", String(topK));
  fd.append("consent_given", String(consentGiven));
  return postForm("/api/face/search", fd);
}
