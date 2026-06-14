// The frontend's single source of truth for values the backend owns elsewhere — keep them in sync when they change.

// Active set fallback when the live set isn't yet known from the network
export const ACTIVE_SET_CODE = "SOS";

// Site name and the title separator. functions/_middleware.ts imports these too, so the
// browser tab (set by DocumentTitle) and the link-unfurl title render the exact same string.
export const SITE_NAME = "Limited Level-Ups";
export const TITLE_SEPARATOR = " | ";

// LLU community Discord guild
export const DISCORD_GUILD_ID = "775371722065051658";

// 17Lands tier-list ids per set, taken from a tier list's share link
// (https://www.17lands.com/tier_list/<uid>). Add one as each set rotates in.
export const TIER_LIST_UIDS: Record<string, string> = {
  SOS: "e195401b1eaa48e3b5d6670e0ae338e9",
  TMT: "fd5499ae88854ca0ac1bc2ad95ade9b2",
  ECL: "1745e64176864bb2bec132cbd601b604",
  TLA: "efdfa8408fb448be846ac06f9d9192ff",
};

// Tier lists can publish before a set is registered backend-side (preview window).
// These supply name/date for such codes until they show up in the live sets feed.
export const TIER_LIST_PREVIEW_SETS: Record<string, { name: string; startDate: string }> = {};

// CORS-enabled 17Lands endpoint returning a tier list's card ratings array
export const TIER_LIST_DATA_BASE = "https://www.17lands.com/card_tiers/data";

// Per-uid data-endpoint overrides for tier lists served elsewhere (e.g. a local
// preview server for a set not yet public on 17Lands). Fetch becomes `${base}/${uid}`.
export const TIER_LIST_DATA_BASE_OVERRIDES: Record<string, string> = {};
