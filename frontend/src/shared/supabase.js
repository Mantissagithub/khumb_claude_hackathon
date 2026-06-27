import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  console.error("Missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY");
}

// Two independent clients so staff and public sessions never collide in one
// browser (separate storageKey = separate persisted session).
export const supabase = createClient(url, key, {
  auth: { persistSession: true, autoRefreshToken: true, storageKey: "sangam-staff" },
});

export const supabasePublic = createClient(url, key, {
  auth: { persistSession: true, autoRefreshToken: true, storageKey: "sangam-public" },
});

export const FUNCTIONS_URL = `${url}/functions/v1`;
export const ANON_KEY = key;
