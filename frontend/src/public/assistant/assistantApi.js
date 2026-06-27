// Voice/chat assistant — calls the `ai-assistant` Edge Function (Claude lives
// server-side; the API key never reaches the browser).
import { FUNCTIONS_URL, ANON_KEY } from "@/shared/supabase";

export async function askAssistant(messages, lang) {
  const res = await fetch(`${FUNCTIONS_URL}/ai-assistant`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: ANON_KEY,
      Authorization: `Bearer ${ANON_KEY}`,
    },
    body: JSON.stringify({ messages, lang }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Assistant failed");
  return data; // { reply, navigate, report_type }
}
