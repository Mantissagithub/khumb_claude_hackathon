// Shared helpers for the Sahayak web app (no framework — vanilla JS).
const API = location.origin;

async function jget(p) { return (await fetch(API + p)).json(); }
async function jpost(p, body) {
  return (await fetch(API + p, { method: "POST", body })).json();
}
function $(sel, root = document) { return root.querySelector(sel); }
function $all(sel, root = document) { return [...root.querySelectorAll(sel)]; }

const BAND = {
  STRONG: { c: "bg-emerald-100 text-emerald-800 border-emerald-300", dot: "bg-emerald-500" },
  LIKELY: { c: "bg-green-100 text-green-800 border-green-300", dot: "bg-green-500" },
  POSSIBLE: { c: "bg-amber-100 text-amber-800 border-amber-300", dot: "bg-amber-500" },
  NO_MATCH: { c: "bg-rose-100 text-rose-800 border-rose-300", dot: "bg-rose-500" },
};
function bandClass(b) { return (BAND[b] || BAND.NO_MATCH).c; }

// Toast notifications -------------------------------------------------------
function toast(msg, type = "info", ms = 6000) {
  let host = $("#toasts");
  if (!host) {
    host = document.createElement("div");
    host.id = "toasts";
    host.className = "fixed top-4 right-4 z-50 flex flex-col gap-2 w-80";
    document.body.appendChild(host);
  }
  const colors = {
    info: "bg-indigo-600", success: "bg-emerald-600",
    warn: "bg-amber-500", error: "bg-rose-600",
  };
  const t = document.createElement("div");
  t.className = `toast text-white rounded-xl shadow-lg px-4 py-3 ${colors[type] || colors.info}`;
  t.innerHTML = msg;
  host.appendChild(t);
  setTimeout(() => { t.style.opacity = "0"; setTimeout(() => t.remove(), 300); }, ms);
}

// WebSocket with auto-reconnect + heartbeat --------------------------------
function connectWS({ role, center, onEvent, onStatus }) {
  let ws, hb, alive = true;
  const url = (location.protocol === "https:" ? "wss" : "ws") + "://" + location.host
    + "/ws?" + (role ? "role=" + role : "center=" + encodeURIComponent(center));
  function open() {
    ws = new WebSocket(url);
    ws.onopen = () => { onStatus && onStatus(true); hb = setInterval(() => ws.readyState === 1 && ws.send("ping"), 20000); };
    ws.onmessage = (e) => { try { const m = JSON.parse(e.data); onEvent && onEvent(m.event, m.data); } catch {} };
    ws.onclose = () => { onStatus && onStatus(false); clearInterval(hb); if (alive) setTimeout(open, 1500); };
    ws.onerror = () => ws.close();
  }
  open();
  return { close: () => { alive = false; ws && ws.close(); } };
}

function initials(name) { return (name || "?").trim().slice(0, 1).toUpperCase() || "?"; }
function photoUrl(caseId) { return `${API}/api/cases/${caseId}/photo`; }
