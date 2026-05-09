import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// Single Supabase client for the whole app. Initialized only when both env
// vars are set; otherwise the rest of the data layer falls back to the fixture
// API so dev without Supabase still works.
//
// Vite exposes any env var prefixed with VITE_ to the client bundle. The
// service-role key never appears here — only the anon key, which can only
// SELECT from the curated public_* views (per spec § RLS / grants).

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const supabase: SupabaseClient | null =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: { persistSession: false },
      })
    : null;

export const useSupabase = supabase !== null;
