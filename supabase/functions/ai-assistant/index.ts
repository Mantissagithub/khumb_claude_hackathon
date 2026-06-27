// ─────────────────────────────────────────────────────────────
// ai-assistant — voice/chat helper for the SANGAM public surface.
// Browser sends the conversation; this proxies to Claude (key held
// server-side as the ANTHROPIC_API_KEY secret) and returns a short
// spoken reply plus an optional navigation target.
// ─────────────────────────────────────────────────────────────
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (b: unknown, s = 200) =>
  new Response(JSON.stringify(b), { status: s, headers: { ...cors, "Content-Type": "application/json" } });

const LANG_NAME: Record<string, string> = { en: "English", hi: "Hindi", mr: "Marathi" };

const navigateTool = {
  name: "navigate",
  description:
    "Take the user to a page in the SANGAM app. Call this whenever the user wants to go somewhere or do something that lives on a specific page.",
  input_schema: {
    type: "object",
    properties: {
      route: {
        type: "string",
        enum: ["/", "/new", "/track", "/reports"],
        description:
          "/ = home. /new = file a new report. /track = log in with phone to view reports. /reports = the list of the user's own reports (needs login).",
      },
      report_type: {
        type: "string",
        enum: ["lost_self", "seeking", "found"],
        description:
          "Only when route is /new. lost_self = the speaker is themselves lost; seeking = searching for a missing person; found = they found a lost person.",
      },
    },
    required: ["route"],
  },
};

function systemPrompt(lang: string) {
  const langName = LANG_NAME[lang] || "English";
  return `You are the voice helper for SANGAM, an app that reunites people separated at the Kumbh Mela (a huge pilgrimage; many users are elderly, rural, and distressed).

Your job: understand what the person needs and guide them to the right page by calling the "navigate" tool, then reassure them in one or two short, simple sentences.

Pages:
- "/" — home
- "/new" — file a report. Choose report_type: "lost_self" if the speaker says they themselves are lost; "seeking" if they are looking for a missing family member or friend; "found" if they have found a lost person.
- "/track" — log in with a phone number to view reports.
- "/reports" — the list of the user's own reports (only after they have logged in; if unsure, use /track).

Rules:
- ALWAYS reply with one or two short, warm, plain sentences a stressed, non-technical person can follow. No lists, no markdown, no jargon.
- Call "navigate" whenever the request maps to a page. If they are just chatting or it is unclear, ask one simple clarifying question instead of navigating.
- Reply ONLY in ${langName}. Output only the spoken reply text — no reasoning, no preamble.
- The emergency helpline is 1920; mention it if someone seems to be in immediate danger.`;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    if (!ANTHROPIC_API_KEY) return json({ error: "Assistant is not configured" }, 500);
    const body = await req.json();
    const lang = String(body.lang || "en");
    const messages = Array.isArray(body.messages) ? body.messages : [];
    if (messages.length === 0) return json({ error: "No message" }, 400);

    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-opus-4-8",
        max_tokens: 400,
        output_config: { effort: "low" },
        system: systemPrompt(lang),
        tools: [navigateTool],
        messages: messages.map((m: { role: string; content: string }) => ({
          role: m.role === "assistant" ? "assistant" : "user",
          content: String(m.content ?? ""),
        })),
      }),
    });

    const data = await resp.json();
    if (!resp.ok) return json({ error: data?.error?.message || "Assistant failed" }, 502);

    let reply = "";
    let navigate: string | null = null;
    let report_type: string | null = null;
    for (const block of data.content ?? []) {
      if (block.type === "text") reply += block.text;
      else if (block.type === "tool_use" && block.name === "navigate") {
        navigate = block.input?.route ?? null;
        report_type = block.input?.report_type ?? null;
      }
    }

    return json({ reply: reply.trim(), navigate, report_type });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
