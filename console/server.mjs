/**
 * Setu deployment planner backend — minimal Node HTTP server.
 * Exposes POST /api/plan; calls Claude (Anthropic Messages API) or falls back
 * to a greedy heuristic when no API key is present or the call fails.
 *
 * Start with: node server.mjs
 */

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// -------------------------------------------------------------------------- //
// Env loading: read ../.env + process.env
// -------------------------------------------------------------------------- //
function loadDotEnv(filePath) {
  try {
    const text = fs.readFileSync(filePath, "utf8");
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;
      const eq = trimmed.indexOf("=");
      if (eq < 0) continue;
      const key = trimmed.slice(0, eq).trim();
      const val = trimmed.slice(eq + 1).trim();
      if (key && !(key in process.env)) {
        process.env[key] = val;
      }
    }
  } catch (_) {
    // .env is optional
  }
}

loadDotEnv(path.resolve(__dirname, "../.env"));

const API_KEY =
  process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN || "";
const BASE_URL = (
  process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com"
).replace(/\/$/, "");
const MODEL = "claude-sonnet-4-6";

console.log(
  `[server] API key ${API_KEY ? "FOUND" : "NOT FOUND — heuristic only"}`
);

// -------------------------------------------------------------------------- //
// Heuristic fallback
// -------------------------------------------------------------------------- //
function heuristicPlan(hotspots) {
  const sorted = [...hotspots].sort((a, b) => b.w - a.w).slice(0, 3);
  const posts = sorted.map((h) => ({
    lng: h.lng,
    lat: h.lat,
    unit_type: "squad",
    reason: `Highest-weight separation cluster (w=${h.w.toFixed(2)}) at the throat.`,
  }));
  const rationale =
    "Greedy coverage of the highest-density separation clusters at the throat: " +
    "squads placed at the top-3 hotspots by accumulated separation weight. " +
    "No API key configured; heuristic fallback active.";
  return { posts, rationale, source: "heuristic" };
}

// -------------------------------------------------------------------------- //
// Claude call
// -------------------------------------------------------------------------- //
async function claudePlan(hotspots, police, situation) {
  const tool = {
    name: "submit_deployment_plan",
    description:
      "Submit a police deployment plan as structured JSON for the Ramkund ghat corridor.",
    input_schema: {
      type: "object",
      properties: {
        posts: {
          type: "array",
          description: "Up to 3 police deployment posts.",
          items: {
            type: "object",
            properties: {
              lng: { type: "number" },
              lat: { type: "number" },
              unit_type: {
                type: "string",
                enum: ["constable", "squad", "barricade"],
              },
              reason: {
                type: "string",
                description: "Why this post at this location.",
              },
            },
            required: ["lng", "lat", "unit_type", "reason"],
            additionalProperties: false,
          },
        },
        rationale: {
          type: "string",
          description: "One-paragraph operational rationale for the overall plan.",
        },
      },
      required: ["posts", "rationale"],
      additionalProperties: false,
    },
  };

  const userMsg =
    `You are a crowd-safety controller planning police deployment for the Ramkund ghat ` +
    `(Nashik Kumbh 2027).\n\n` +
    `Separation hotspots (lng/lat/weight):\n${JSON.stringify(hotspots, null, 2)}\n\n` +
    `Available police stations:\n${JSON.stringify(police, null, 2)}\n\n` +
    `Live situation:\n${JSON.stringify(situation, null, 2)}\n\n` +
    `Choose up to 3 deployment posts (prefer the highest-weight hotspots / the throat), ` +
    `assign a unit_type to each (constable=small footprint, squad=larger, barricade=metering gate), ` +
    `and give a one-paragraph operational rationale. Call submit_deployment_plan.`;

  const resp = await fetch(`${BASE_URL}/v1/messages`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": API_KEY,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1024,
      tools: [tool],
      tool_choice: { type: "tool", name: "submit_deployment_plan" },
      messages: [{ role: "user", content: userMsg }],
    }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Anthropic API ${resp.status}: ${text}`);
  }

  const data = await resp.json();
  for (const block of data.content ?? []) {
    if (block.type === "tool_use" && block.name === "submit_deployment_plan") {
      return { ...block.input, source: "claude" };
    }
  }
  throw new Error("Claude did not return a deployment plan tool call");
}

// -------------------------------------------------------------------------- //
// CORS helpers
// -------------------------------------------------------------------------- //
function setCors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
}

// -------------------------------------------------------------------------- //
// HTTP server
// -------------------------------------------------------------------------- //
const PORT = 8787;

const server = http.createServer(async (req, res) => {
  setCors(res);

  // preflight
  if (req.method === "OPTIONS") {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method === "POST" && req.url === "/api/plan") {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", async () => {
      let parsed;
      try {
        parsed = JSON.parse(body);
      } catch (_) {
        res.writeHead(400, { "content-type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON" }));
        return;
      }

      const { hotspots = [], police = [], situation = {} } = parsed;

      let result;
      try {
        if (!API_KEY) throw new Error("No API key");
        result = await claudePlan(hotspots, police, situation);
      } catch (err) {
        console.warn(`[server] Claude unavailable (${err.message}); using heuristic.`);
        result = heuristicPlan(hotspots);
      }

      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(result));
    });
    return;
  }

  res.writeHead(404, { "content-type": "application/json" });
  res.end(JSON.stringify({ error: "Not found" }));
});

server.listen(PORT, () => {
  console.log(`[server] Setu planner listening on http://localhost:${PORT}`);
});
