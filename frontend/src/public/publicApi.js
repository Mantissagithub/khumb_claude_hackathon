// ─────────────────────────────────────────────────────────────
// Public (citizen) API — open report submission + phone-OTP viewing.
// Uses the `supabasePublic` client (its own session, separate from staff).
// ─────────────────────────────────────────────────────────────
import { supabasePublic, FUNCTIONS_URL, ANON_KEY } from "@/shared/supabase";

export const normPhone = (p) => (p || "").replace(/\D/g, "");

export const mediaUrl = (p) =>
  p ? supabasePublic.storage.from("photos").getPublicUrl(p).data.publicUrl : null;

async function fn(action, payload) {
  const res = await fetch(`${FUNCTIONS_URL}/auth-phone`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: ANON_KEY,
      Authorization: `Bearer ${ANON_KEY}`,
    },
    body: JSON.stringify({ action, ...payload }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}

// ── Phone OTP (view gate) ──
export const requestOtp = (phone) => fn("request", { phone: normPhone(phone) });

export async function verifyOtp(phone, code) {
  const data = await fn("verify", { phone: normPhone(phone), code });
  await supabasePublic.auth.setSession({
    access_token: data.access_token,
    refresh_token: data.refresh_token,
  });
  return data.phone;
}

export async function currentPhone() {
  const {
    data: { user },
  } = await supabasePublic.auth.getUser();
  return user?.user_metadata?.phone ?? null;
}

export const signOutPublic = () => supabasePublic.auth.signOut();

// ── Photo upload (open) ──
export async function uploadPhoto(file) {
  if (!file) return null;
  const ext = (file.name?.split(".").pop() || "jpg").toLowerCase();
  const fname = `rep_${crypto.randomUUID()}.${ext}`;
  const { error } = await supabasePublic.storage
    .from("photos")
    .upload(fname, file, { contentType: file.type || "image/jpeg" });
  if (error) throw new Error(error.message);
  return fname;
}

// ── Submit a report (open, no login) ──
export async function submitReport(form) {
  const { data, error } = await supabasePublic.rpc("submit_report", {
    p_reporter_phone: normPhone(form.phone),
    p_report_type: form.report_type,
    p_person_name: form.person_name || null,
    p_gender: form.gender || null,
    p_age_band: form.age_band || null,
    p_language: form.language || null,
    p_description: form.description || null,
    p_photo_path: form.photo_path || null,
    p_location_text: form.location_text || null,
    p_lat: form.lat ?? null,
    p_lng: form.lng ?? null,
    p_center_name: form.center_name || null,
  });
  if (error) throw new Error(error.message);
  return data; // new report id
}

// ── View my reports (requires phone session) ──
export async function listMyReports() {
  const { data, error } = await supabasePublic
    .from("reports")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw new Error(error.message);
  return data;
}

export async function getMyReport(id) {
  const { data, error } = await supabasePublic
    .from("reports")
    .select("*")
    .eq("id", id)
    .single();
  if (error) throw new Error(error.message);
  return data;
}
