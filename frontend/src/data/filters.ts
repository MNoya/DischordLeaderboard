// Shared filter option lists and archetype metadata.
// Keep this file as the single source of truth so dropdowns and switchers
// can never drift out of sync.

export interface FilterOption {
  value: string;
  label: string;
}

// Format groups recognized across pages. `value` matches the backend
// `format_label` and the prefix-match used in PlayerPage's draft log filter.
export const FORMAT_OPTIONS: FilterOption[] = [
  { value: "ALL", label: "ALL" },
  { value: "Premier", label: "PREMIER" },
  { value: "Trad", label: "TRADITIONAL" },
  { value: "Quick", label: "QUICK" },
  { value: "Sealed", label: "SEALED" },
  { value: "LCQ", label: "LCQ" },
];

// Same set with the long-form ALL label for the player profile draft log.
export const FORMAT_OPTIONS_LONG: FilterOption[] = [
  { value: "ALL", label: "ALL FORMATS" },
  ...FORMAT_OPTIONS.slice(1),
];

// Two-color archetype codes in WUBRG-pair order (10 guilds).
export const TWO_COLOR_ARCHETYPES: string[] = [
  "WU", "WB", "WR", "WG",
  "UB", "UR", "UG",
  "BR", "BG",
  "RG",
];

// Mono-color archetypes.
export const MONO_ARCHETYPES: string[] = ["W", "U", "B", "R", "G"];

// Three-color "shard/wedge" archetype codes (informational; not always rendered).
export const TRI_COLOR_ARCHETYPES: string[] = [
  "WUB", "WUR", "WUG",
  "WBR", "WBG", "WRG",
  "UBR", "UBG", "URG",
  "BRG",
];

// Filter dropdown options for archetype scoping.
export const ARCHETYPE_OPTIONS: FilterOption[] = [
  { value: "ALL", label: "ALL" },
  ...TWO_COLOR_ARCHETYPES.map((a) => ({ value: a, label: a })),
];

export const ARCHETYPE_OPTIONS_LONG: FilterOption[] = [
  { value: "ALL", label: "ALL ARCHETYPES" },
  ...TWO_COLOR_ARCHETYPES.map((a) => ({ value: a, label: a })),
];

// Display names for two-color archetypes (the MTG guild names).
// Used in the archetype board hero and the leaderboard sidebar.
export const ARCHETYPE_NAMES: Record<string, string> = {
  WU: "AZORIUS",
  WB: "ORZHOV",
  WR: "BOROS",
  WG: "SELESNYA",
  UB: "DIMIR",
  UR: "IZZET",
  UG: "SIMIC",
  BR: "RAKDOS",
  BG: "GOLGARI",
  RG: "GRUUL",
};
