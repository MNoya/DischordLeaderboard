import type { SetSummary } from "../types/leaderboard";

// MTGO-only flashback drafts, never on Arena and never in the leaderboard rotation. Mirrors the
// bot's bot/sets.py MTGO_FLASHBACK_SETS — keep the two in sync. Trophies logged against these codes
// are showcase-only and rank on a trophy-count board rather than the scored leaderboard.
export const MTGO_FLASHBACK_SETS: Record<string, string> = {
  IPA: "Invasion Block",
  USG: "Urza's Saga Block",
  MH1: "Modern Horizons",
  MH2: "Modern Horizons 2",
};

export const isMtgoFlashbackCode = (code: string): boolean => code.toUpperCase() in MTGO_FLASHBACK_SETS;

export const mtgoSetName = (code: string): string => MTGO_FLASHBACK_SETS[code.toUpperCase()] ?? code.toUpperCase();

// Original release date of each flashback set's lead set, shown on the switcher chip. Sorting pins
// MTGO sets to the bottom of the switcher regardless (see SetSwitcher), so these are display-only.
const MTGO_RELEASE_DATE: Record<string, string> = {
  MH1: "2019-06-14",
  MH2: "2021-06-18",
  USG: "1998-10-12",
  IPA: "2000-10-02",
};

// Synthetic SetSummary rows so MTGO flashback boards appear in the set switchers without a public_sets
// entry. Only codes with logged trophies are passed in, so empty boards never clutter the switcher.
export function withMtgoSets(sets: SetSummary[] | undefined, codes: string[] | undefined): SetSummary[] | undefined {
  if (!sets || !codes || codes.length === 0) {
    return sets;
  }
  const known = new Set(sets.map((s) => s.code));
  const extra: SetSummary[] = codes
    .filter((c) => isMtgoFlashbackCode(c) && !known.has(c.toUpperCase()))
    .map((c) => {
      const code = c.toUpperCase();
      const released = MTGO_RELEASE_DATE[code] ?? "";
      return { code, name: mtgoSetName(c), startDate: released, endDate: released, isActive: false };
    });
  return extra.length ? [...sets, ...extra] : sets;
}
