import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import {
  PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  PUBLIC_SUPABASE_URL,
} from "./public-supabase-config";

// Single Supabase client for the whole app. Always initialized in production
// using the public defaults from public-supabase-config.ts; in local dev,
// VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY (e.g. via .env.local)
// override the defaults for staging projects or fixture-only mode.
//
// The "publishable" key hits the anon role server-side and can only SELECT
// from the curated public_* views (per spec § RLS / grants). It is by design
// safe to embed in the client bundle.

const url = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? PUBLIC_SUPABASE_URL;
const publishableKey =
  (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined) ??
  PUBLIC_SUPABASE_PUBLISHABLE_KEY;

export const supabase: SupabaseClient | null =
  url && publishableKey
    ? createClient(url, publishableKey, {
        auth: { persistSession: false },
      })
    : null;

export const useSupabase = supabase !== null;
