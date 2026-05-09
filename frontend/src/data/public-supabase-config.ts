// Public Supabase configuration — these values ARE the client-side bundle's
// credentials and are designed to be visible in every browser that loads the
// site. They are NOT secrets. Checking them in matches their actual security
// posture and removes a deploy-time configuration step.
//
// Why this is safe:
//   1. The URL is the project's public REST endpoint.
//   2. The "publishable" key is Supabase's browser-facing anon credential.
//      Per https://supabase.com/docs/guides/api/api-keys it is designed to be
//      embedded in client bundles. The legacy name was "anon JWT".
//   3. All data access is gated by Row-Level Security on the underlying tables
//      and SELECT-only grants on the curated public_* views (frontend-spec.md
//      → RLS / grants). The publishable key cannot read base tables, write
//      anything, or escalate to service-role access.
//
// To rotate: replace the publishable key in Supabase dashboard → Settings →
// API → Publishable key, then update the constant below. The previous key
// continues working for ~5 minutes; the rotation is non-breaking.
//
// Local dev with VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY env vars
// (e.g. .env.local) overrides these defaults, so contributors targeting a
// staging project don't need to edit this file.

export const PUBLIC_SUPABASE_URL = "https://yrecdosksgigpceholjl.supabase.co";

export const PUBLIC_SUPABASE_PUBLISHABLE_KEY =
  "sb_publishable_x-W4800MtS_hbFAnLmAk6Q_68P4Nxsf";
