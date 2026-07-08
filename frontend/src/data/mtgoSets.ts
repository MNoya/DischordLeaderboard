import type { SetSummary } from "../types/leaderboard";

// MTGO-only flashback drafts, never on Arena and never in the leaderboard rotation. Mirrors the
// bot's bot/sets.py MTGO_FLASHBACK_SETS — keep the two in sync. Trophies logged against these codes
// are showcase-only and rank on a trophy-count board rather than the scored leaderboard.
export const MTGO_FLASHBACK_SETS: Record<string, string> = {
  IPA: "Invasion Block",
  USG: "Urza Block",
  MH1: "Modern Horizons",
  MH2: "Modern Horizons 2",
};

export const isMtgoFlashbackCode = (code: string): boolean => code.toUpperCase() in MTGO_FLASHBACK_SETS;

export const mtgoSetName = (code: string): string => MTGO_FLASHBACK_SETS[code.toUpperCase()] ?? code.toUpperCase();

// Constituent set glyphs (keyrune classes) for block flashback drafts, shown together in the board
// hero so a block reads as its member sets. Single-set flashbacks are absent and use their own glyph.
export const MTGO_BLOCK_GLYPHS: Record<string, string[]> = {
  IPA: ["inv", "pls", "apc"],
  USG: ["usg", "ulg", "uds"],
};

// Release date shown on the switcher chip. For a block draft it's the block's final set (IPA ->
// Apocalypse, USG -> Urza's Destiny); single-set flashbacks use their own date. Sorting pins MTGO
// sets to the bottom of the switcher regardless (see SetSwitcher), so these are display-only.
const MTGO_RELEASE_DATE: Record<string, string> = {
  MH1: "2019-06-14",
  MH2: "2021-06-18",
  USG: "1999-06-07",
  IPA: "2001-06-04",
};

// Synthetic SetSummary rows so every MTGO flashback board appears in the set switchers without a
// public_sets entry, shown by default whether or not any trophy has been logged for them yet.
export function withMtgoSets(sets: SetSummary[] | undefined): SetSummary[] | undefined {
  if (!sets) {
    return sets;
  }
  const known = new Set(sets.map((s) => s.code));
  const extra: SetSummary[] = Object.keys(MTGO_FLASHBACK_SETS)
    .filter((code) => !known.has(code))
    .map((code) => {
      const released = MTGO_RELEASE_DATE[code] ?? "";
      return { code, name: mtgoSetName(code), startDate: released, endDate: released, isActive: false };
    });
  return extra.length ? [...sets, ...extra] : sets;
}
