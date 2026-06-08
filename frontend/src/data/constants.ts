// The frontend's single source of truth for values the backend owns elsewhere — keep them in sync when they change.

// Active set fallback when the live set isn't yet known from the network
export const ACTIVE_SET_CODE = "SOS";

// LLU community Discord guild
export const DISCORD_GUILD_ID = "775371722065051658";

// 17Lands tier-list embed ids per set, taken from a tier list's embed link
// (https://www.17lands.com/card_tiers/embedded/<uid>). Add one as each set rotates in.
export const TIER_LIST_UIDS: Record<string, string> = {
  SOS: "e195401b1eaa48e3b5d6670e0ae338e9",
  TMT: "fd5499ae88854ca0ac1bc2ad95ade9b2",
  ECL: "1745e64176864bb2bec132cbd601b604",
  TLA: "efdfa8408fb448be846ac06f9d9192ff",
};

export const TIER_LIST_EMBED_BASE = "https://www.17lands.com/card_tiers/embedded";

// Fallback iframe height until the embed posts its real height via postMessage; sized to clear the longest measured tier list
export const TIER_LIST_EMBED_HEIGHT = 2950;

// Fixed iframe width on mobile so every color column stays legible and the wrapper scrolls horizontally to reach them
export const TIER_LIST_EMBED_MOBILE_WIDTH = 760;
