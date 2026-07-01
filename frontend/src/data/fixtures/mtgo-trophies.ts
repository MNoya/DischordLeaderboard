import type { SelfReportedTrophy, TrophyLeaderboardRow } from "../../types/leaderboard";

// Synthetic MTGO flashback trophy boards for mock mode (VITE_DATA_MODE=mock). Fictional players.

let seq = 0;

const deck = (setCode: string, colors: string, record: string, reportedAt: string): SelfReportedTrophy => ({
  setCode,
  record,
  colors,
  platform: "MTGO",
  caption: null,
  screenshotUrl: null,
  sourceChannelId: "0",
  sourceMessageId: String(++seq),
  sourceUrl: "#",
  reportedAt,
});

const rank = (rows: Omit<TrophyLeaderboardRow, "rank">[]): TrophyLeaderboardRow[] =>
  [...rows]
    .sort((a, b) => b.trophies - a.trophies || b.decks[0].reportedAt.localeCompare(a.decks[0].reportedAt))
    .map((r, i) => ({ ...r, rank: i + 1 }));

const player = (
  setCode: string,
  slug: string,
  displayName: string,
  decks: SelfReportedTrophy[],
): Omit<TrophyLeaderboardRow, "rank"> => ({
  setCode,
  slug,
  displayName,
  avatarUrl: null,
  trophies: decks.length,
  decks,
});

export const MTGO_TROPHY_FIXTURE: Record<string, TrophyLeaderboardRow[]> = {
  MH1: rank([
    player("MH1", "sythe", "Sythe", [
      deck("MH1", "UR", "3-0", "2026-06-20T14:00:00Z"),
      deck("MH1", "WUb", "3-1", "2026-06-14T14:00:00Z"),
      deck("MH1", "BG", "3-0", "2026-06-02T14:00:00Z"),
    ]),
    player("MH1", "orlok", "Orlok", [
      deck("MH1", "BR", "3-0", "2026-06-18T14:00:00Z"),
      deck("MH1", "WU", "3-2", "2026-06-09T14:00:00Z"),
    ]),
    player("MH1", "vessa", "Vessa", [deck("MH1", "WUBRG", "3-1", "2026-06-11T14:00:00Z")]),
  ]),
  MH2: rank([
    player("MH2", "orlok", "Orlok", [
      deck("MH2", "UG", "3-0", "2026-06-22T14:00:00Z"),
      deck("MH2", "Rw", "3-0", "2026-06-15T14:00:00Z"),
    ]),
    player("MH2", "kaldo", "Kaldo", [deck("MH2", "WB", "3-1", "2026-06-19T14:00:00Z")]),
    player("MH2", "sythe", "Sythe", [deck("MH2", "BR", "3-0", "2026-06-08T14:00:00Z")]),
  ]),
  USG: rank([
    player("USG", "brenn", "Brenn", [
      deck("USG", "UB", "3-0", "2026-06-21T14:00:00Z"),
      deck("USG", "WG", "3-1", "2026-06-10T14:00:00Z"),
    ]),
    player("USG", "vessa", "Vessa", [deck("USG", "UR", "3-0", "2026-06-17T14:00:00Z")]),
  ]),
  IPA: rank([
    player("IPA", "kaldo", "Kaldo", [deck("IPA", "WUBRG", "3-1", "2026-06-16T14:00:00Z")]),
    player("IPA", "brenn", "Brenn", [deck("IPA", "BR", "3-0", "2026-06-05T14:00:00Z")]),
  ]),
};
