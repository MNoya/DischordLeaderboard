// Shared filter option lists and color-combo metadata.
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
  { value: "Premier", label: "PREMIER DRAFT" },
  { value: "Trad", label: "TRADITIONAL DRAFT" },
  { value: "Quick", label: "QUICK DRAFT" },
  { value: "Sealed", label: "SEALED" },
  { value: "LCQ", label: "CHAMPIONSHIP QUALIFIER" },
];

// Same set with the long-form ALL label for the player profile draft log.
export const FORMAT_OPTIONS_LONG: FilterOption[] = [
  { value: "ALL", label: "ALL FORMATS" },
  ...FORMAT_OPTIONS.slice(1),
];

// Cross-cutting bucket — any deck with ≥4 effective colors. Display label: "SOUP"
export const MULTI = "MULTI";

// Client-side catchall for sub-threshold combos. Display label: "OTHER"
export const OTHER = "OTHER";

// Mono-color codes (rare in modern Limited; kept for completeness).
export const MONO_COLOR_CODES: string[] = ["W", "U", "B", "R", "G"];

// Two-color codes in WUBRG-pair order (10 guilds).
export const TWO_COLOR_CODES: string[] = [
  "WU", "WB", "WR", "WG",
  "UB", "UR", "UG",
  "BR", "BG",
  "RG",
];

// Three-color shard/wedge codes (informational; not all formats support them).
export const TRI_COLOR_CODES: string[] = [
  "WUB", "WUR", "WUG",
  "WBR", "WBG", "WRG",
  "UBR", "UBG", "URG",
  "BRG",
];

// Display names for mono-color codes.
const MONO_NAMES: Record<string, string> = {
  W: "MONO WHITE",
  U: "MONO BLUE",
  B: "MONO BLACK",
  R: "MONO RED",
  G: "MONO GREEN",
};

// Display names for two-color codes (the MTG guild names).
const GUILD_NAMES: Record<string, string> = {
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

// Three-color shard/wedge names. Used by the deck-colors charts when a player
// drafts a 3-color deck.
const WEDGE_NAMES: Record<string, string> = {
  WUB: "ESPER",
  WUR: "JESKAI",
  WUG: "BANT",
  WBR: "MARDU",
  WBG: "ABZAN",
  WRG: "NAYA",
  UBR: "GRIXIS",
  UBG: "SULTAI",
  URG: "TEMUR",
  BRG: "JUND",
};

export function colorsDisplayName(code: string): string {
  if (code === MULTI) return "SOUP";
  if (code === OTHER) return "OTHER";
  if (MONO_NAMES[code]) return MONO_NAMES[code];
  if (GUILD_NAMES[code]) return GUILD_NAMES[code];
  if (WEDGE_NAMES[code]) return WEDGE_NAMES[code];
  if (code === "WUBRG") return "5-COLOR";
  return code;
}

const _wubrgSort = (s: string) =>
  [...s].sort((a, b) => "WUBRG".indexOf(a) - "WUBRG".indexOf(b)).join("");

// "URg" → "IZZET SPLASH G", "UGbr" → "SIMIC SPLASH BR", "WB" → "ORZHOV"
export function formatDeckColors(colors: string | null | undefined): string {
  const { name, splash } = deckColorParts(colors);
  return splash ? `${name} ${splash}` : name;
}

// Same data as formatDeckColors but split for column-aligned layouts.
// `splash` is "SPLASH X" / "" — already includes the prefix word for readability.
export function deckColorParts(colors: string | null | undefined): { name: string; splash: string } {
  if (!colors) return { name: "", splash: "" };
  const main = _wubrgSort(colors.replace(/[a-z]/g, ""));
  const splash = _wubrgSort(colors.replace(/[A-Z]/g, "").toUpperCase());
  const name = main ? colorsDisplayName(main) : "COLORLESS";
  return { name, splash: splash ? `SPLASH ${splash}` : "" };
}

const comboLabel = (code: string) => `${code} · ${colorsDisplayName(code)}`;

export const COLOR_OPTIONS: FilterOption[] = [
  { value: "ALL", label: "ALL" },
  ...TWO_COLOR_CODES.map((c) => ({ value: c, label: comboLabel(c) })),
];

export const COLOR_OPTIONS_LONG: FilterOption[] = [
  { value: "ALL", label: "ALL COLORS" },
  ...TWO_COLOR_CODES.map((c) => ({ value: c, label: comboLabel(c) })),
];
