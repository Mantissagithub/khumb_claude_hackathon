// ─────────────────────────────────────────────────────────────
// Supabase-native API layer. Same function names the pages already
// import — implementations now hit Supabase directly (Auth + Postgres
// + Storage + RPC + the staff-admin Edge Function). No FastAPI.
// ─────────────────────────────────────────────────────────────
import { supabase } from "@/shared/supabase";

const EMAIL_DOMAIN = "@sangam.local";
const toEmail = (u) => (u.includes("@") ? u : `${u.trim()}${EMAIL_DOMAIN}`);

// Resolve a stored photo path (Storage object key) to a public URL.
export const mediaUrl = (p) =>
  p ? supabase.storage.from("photos").getPublicUrl(p).data.publicUrl : null;

async function fetchProfile(id) {
  const { data, error } = await supabase
    .from("profiles")
    .select("role,name")
    .eq("id", id)
    .single();
  if (error) throw error;
  return data;
}

// ── Auth ──
export async function login(username, password) {
  const email = toEmail(username);
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error("Incorrect username or password");
  const profile = await fetchProfile(data.user.id);
  return { role: profile.role, name: profile.name };
}

export async function me() {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) throw new Error("Not signed in");
  const p = await fetchProfile(user.id);
  return { username: user.email, role: p.role, name: p.name };
}

export const logout = () => supabase.auth.signOut();

async function currentUserId() {
  const {
    data: { user },
  } = await supabase.auth.getUser();
  return user?.id ?? null;
}

// ── Public (no auth) ──
export async function submitPublic(form) {
  const get = (k) => {
    const v = form.get(k);
    return v === null || v === "" ? null : v;
  };
  if (get("hp")) return { ok: true, submission_id: null }; // honeypot

  let photo_path = null;
  const photo = form.get("photo");
  if (photo && photo.size) {
    const ext = (photo.name?.split(".").pop() || "jpg").toLowerCase();
    const fname = `sub_${crypto.randomUUID()}.${ext}`;
    const { error: upErr } = await supabase.storage
      .from("photos")
      .upload(fname, photo, { contentType: photo.type || "image/jpeg" });
    if (!upErr) photo_path = fname;
  }

  const row = {
    missing_name: get("missing_name"),
    gender: get("gender"),
    age_band: get("age_band"),
    last_seen_location: get("last_seen_location"),
    physical_description: get("physical_description"),
    reporter_name: get("reporter_name"),
    reporter_phone: get("reporter_phone"),
    photo_path,
  };
  const { data, error } = await supabase
    .from("submissions")
    .insert(row)
    .select("id")
    .single();
  if (error) throw new Error(error.message);
  return { ok: true, submission_id: data.id };
}

// ── Submissions queue (staff) ──
export async function listSubmissions(status = "", q = "") {
  let query = supabase.from("submissions").select("*").order("created_at", { ascending: false });
  if (status) query = query.eq("review_status", status);
  if (q)
    query = query.or(
      `missing_name.ilike.%${q}%,physical_description.ilike.%${q}%,last_seen_location.ilike.%${q}%`
    );
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return { items: data, total: data.length };
}

export async function getSubmission(id) {
  const { data, error } = await supabase.from("submissions").select("*").eq("id", id).single();
  if (error) throw new Error(error.message);
  return data;
}

export async function runMatch(id, top_n = 5) {
  const { data, error } = await supabase.rpc("match_submission", { p_sub_id: id, p_top_n: top_n });
  if (error) throw new Error(error.message);
  const candidates = (data ?? []).map((c) => ({ ...c, score: Number(c.score) }));
  return { submission_id: id, candidates };
}

export async function confirmMatch(id, case_id, note) {
  const uid = await currentUserId();
  const { error } = await supabase
    .from("submissions")
    .update({
      review_status: "matched",
      matched_case_id: case_id,
      reviewed_by: uid,
      reviewed_at: new Date().toISOString(),
      decision_note: note,
    })
    .eq("id", id);
  if (error) throw new Error(error.message);
  await supabase.from("cases").update({ status: "Matched" }).eq("case_id", case_id);
  return { ok: true, matched_case_id: case_id };
}

export async function promote(id, note) {
  const { data: sub, error: sErr } = await supabase
    .from("submissions")
    .select("*")
    .eq("id", id)
    .single();
  if (sErr) throw new Error(sErr.message);
  const uid = await currentUserId();
  const new_id = `PUB-${String(id).padStart(5, "0")}`;
  const { error: cErr } = await supabase.from("cases").upsert(
    {
      case_id: new_id,
      type: "missing",
      name: sub.missing_name,
      name_normalized: (sub.missing_name || "").toLowerCase().trim(),
      gender: sub.gender,
      age_band: sub.age_band,
      last_seen_location: sub.last_seen_location,
      lat: sub.lat,
      lng: sub.lng,
      zone: sub.zone,
      reporter_mobile: sub.reporter_phone,
      physical_description: sub.physical_description,
      photo_path: sub.photo_path,
      status: "Active",
      reported_at: new Date().toISOString(),
      remarks: `Promoted from public submission #${id}`,
    },
    { onConflict: "case_id" }
  );
  if (cErr) throw new Error(cErr.message);
  const { error: uErr } = await supabase
    .from("submissions")
    .update({
      review_status: "promoted",
      created_case_id: new_id,
      reviewed_by: uid,
      reviewed_at: new Date().toISOString(),
      decision_note: note,
    })
    .eq("id", id);
  if (uErr) throw new Error(uErr.message);
  return { ok: true, created_case_id: new_id };
}

export async function reject(id, note) {
  const uid = await currentUserId();
  const { error } = await supabase
    .from("submissions")
    .update({
      review_status: "rejected",
      reviewed_by: uid,
      reviewed_at: new Date().toISOString(),
      decision_note: note,
    })
    .eq("id", id);
  if (error) throw new Error(error.message);
  return { ok: true };
}

export async function reunite(case_id) {
  const { error } = await supabase.from("cases").update({ status: "Reunited" }).eq("case_id", case_id);
  if (error) throw new Error(error.message);
  return { ok: true, case_id, status: "Reunited" };
}

// ── Cases ──
export async function listCases(params = {}) {
  let query = supabase
    .from("cases")
    .select("*")
    .order("reported_at", { ascending: false })
    .limit(params.limit ?? 50);
  if (params.status) query = query.eq("status", params.status);
  if (params.zone) query = query.eq("zone", params.zone);
  if (params.q)
    query = query.or(
      `name.ilike.%${params.q}%,physical_description.ilike.%${params.q}%,case_id.ilike.%${params.q}%`
    );
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return { items: data, total: data.length };
}

// Lightweight geo points for the admin heatmap — all cases with coords.
export async function casePoints({ status } = {}) {
  let query = supabase
    .from("cases")
    .select("case_id,name,lat,lng,status,zone")
    .not("lat", "is", null)
    .limit(5000);
  if (status) query = query.eq("status", status);
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return data;
}

export async function getCase(case_id) {
  const { data, error } = await supabase.from("cases").select("*").eq("case_id", case_id).single();
  if (error) throw new Error(error.message);
  return data;
}

export async function getReport(id) {
  const { data, error } = await supabase.from("reports").select("*").eq("id", id).single();
  if (error) throw new Error(error.message);
  return data;
}

// ── Claude face matches (report_matches) ──
export async function listReportMatches() {
  const { data, error } = await supabase
    .from("report_matches")
    .select(
      "*, query:reports!report_matches_query_report_id_fkey(*), candidate:reports!report_matches_candidate_report_id_fkey(*)"
    )
    .order("confidence", { ascending: false });
  if (error) throw new Error(error.message);
  return data;
}

// Invoke the Claude vision matcher for one report (manual run / backfill).
export async function runFaceMatch(reportId) {
  const { data, error } = await supabase.functions.invoke("face-match", {
    body: { report_id: reportId },
  });
  if (error) {
    const msg = (await error?.context?.json?.().catch(() => null))?.error;
    throw new Error(msg || error.message);
  }
  return data;
}

export async function setMatchStatus(id, status) {
  const { error } = await supabase.from("report_matches").update({ status }).eq("id", id);
  if (error) throw new Error(error.message);
}

// ── Staff (admin only) ──
export async function listStaff() {
  const { data, error } = await supabase
    .from("staff_view")
    .select("id,name,role,email,created_at")
    .order("created_at");
  if (error) throw new Error(error.message);
  return data.map((s) => ({ ...s, username: s.email }));
}

async function callStaffAdmin(body) {
  const { data, error } = await supabase.functions.invoke("staff-admin", { body });
  if (error) {
    const msg = (await error?.context?.json?.().catch(() => null))?.error;
    throw new Error(msg || error.message || "Staff operation failed");
  }
  if (data?.error) throw new Error(data.error);
  return data;
}

export const createStaff = (body) => callStaffAdmin({ action: "create", ...body });
export const deleteStaff = (id) => callStaffAdmin({ action: "delete", id });

// ── Analytics ──
export async function analytics() {
  const { data, error } = await supabase.rpc("analytics_summary");
  if (error) throw new Error(error.message);
  return data;
}

// ── Public reports review (staff) ──
export async function listReports(status = "", review = "") {
  let query = supabase.from("reports").select("*").order("created_at", { ascending: false });
  if (status) query = query.eq("status", status);
  if (review) query = query.eq("review_status", review);
  const { data, error } = await query;
  if (error) throw new Error(error.message);
  return data;
}

export async function matchReport(id, top_n = 5) {
  const { data, error } = await supabase.rpc("match_report", { p_report_id: id, p_top_n: top_n });
  if (error) throw new Error(error.message);
  return (data ?? []).map((c) => ({ ...c, score: Number(c.score) }));
}

export async function confirmReportMatch(id, source, ref_id, note) {
  const { error } = await supabase.rpc("confirm_report_match", {
    p_report_id: id, p_source: source, p_ref_id: String(ref_id), p_note: note ?? null,
  });
  if (error) throw new Error(error.message);
  return { ok: true };
}

export async function rejectReport(id, note) {
  const { error } = await supabase.rpc("reject_report", { p_report_id: id, p_note: note ?? null });
  if (error) throw new Error(error.message);
  return { ok: true };
}

export async function reuniteReport(id) {
  const { error } = await supabase.rpc("reunite_report", { p_report_id: id });
  if (error) throw new Error(error.message);
  return { ok: true };
}

// reports may carry photos in either bucket key form
export const reportMedia = mediaUrl;
