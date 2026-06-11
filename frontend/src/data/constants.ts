// The frontend's single source of truth for values the backend owns elsewhere — keep them in sync when they change.

// Active set fallback when the live set isn't yet known from the network
export const ACTIVE_SET_CODE = "SOS";

// LLU community Discord guild
export const DISCORD_GUILD_ID = "775371722065051658";

// 17Lands tier-list ids per set, taken from a tier list's share link
// (https://www.17lands.com/tier_list/<uid>). Add one as each set rotates in.
export const TIER_LIST_UIDS: Record<string, string> = {
  MSH: "11bab60203f2410a94a41bb7981bae09",
  SOS: "e195401b1eaa48e3b5d6670e0ae338e9",
  TMT: "fd5499ae88854ca0ac1bc2ad95ade9b2",
  ECL: "1745e64176864bb2bec132cbd601b604",
  TLA: "efdfa8408fb448be846ac06f9d9192ff",
};

// Per-set host graders whose locked set-review lists join onto the consensus by card
// name; shown in the card popup until a card gets its first regrade.
export const TIER_LIST_GRADERS: Record<
  string,
  Array<{ name: string; uid: string }>
> = {
  MSH: [
    { name: "Alex", uid: "4806ce67270a4ea392fd1736bb8e708f" },
    { name: "Marc", uid: "a3c1255425a44f5b866a967f0a5b131e" },
  ],
};

// Tier lists can publish before a set is registered backend-side (preview window).
// These supply name/date for such codes until they show up in the live sets feed.
export const TIER_LIST_PREVIEW_SETS: Record<
  string,
  { name: string; startDate: string }
> = {
  MSH: { name: "Marvel Super Heroes", startDate: "2026-06-23" },
};

// Same-origin proxy to 17Lands' dict-shaped tier-list endpoint (ratings +
// last_updated), which has no CORS headers for direct browser use. Served by
// functions/api/tier-list in prod and a vite proxy entry in dev.
export const TIER_LIST_DATA_BASE = "/api/tier-list";

// Per-uid full fetch URLs for tier lists not served by 17Lands (e.g. a fixture
// snapshot under public/tier-fixtures for a set not yet public upstream).
export const TIER_LIST_DATA_BASE_OVERRIDES: Record<string, string> = {
  "11bab60203f2410a94a41bb7981bae09":
    "/tier-fixtures/11bab60203f2410a94a41bb7981bae09.json",
};
