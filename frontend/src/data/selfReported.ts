import type { LeaderboardRow } from "../types/leaderboard";

// A player's self-reported trophy tally for one set, logged via /trophy. Never scored: folded into
// the leaderboard's trophy count only, so a self-report-only player enters the board at score 0 and
// can top the trophy sort without earning points.
export interface SelfReportedTrophyTally {
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  trophies: number;
}

export const mergeSelfReportedTrophies = (
  rows: LeaderboardRow[],
  tallies: SelfReportedTrophyTally[],
  setCode: string,
): LeaderboardRow[] => {
  const bySlug = new Map(rows.map((r) => [r.slug, { ...r }]));
  for (const tally of tallies) {
    if (tally.trophies === 0) continue;
    const existing = bySlug.get(tally.slug);
    if (existing) {
      existing.trophies += tally.trophies;
    } else {
      bySlug.set(tally.slug, {
        setCode,
        slug: tally.slug,
        displayName: tally.displayName,
        avatarUrl: tally.avatarUrl,
        rank: 0,
        score: 0,
        trophies: tally.trophies,
        events: 0,
        wins: 0,
        losses: 0,
        lastCalculatedAt: new Date(0).toISOString(),
      });
    }
  }
  let rank = 0;
  return [...bySlug.values()]
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.displayName.localeCompare(b.displayName);
    })
    .map((row) => {
      const unscored = row.score === 0;
      if (unscored) return { ...row, rank: 0 };
      rank += 1;
      return { ...row, rank };
    });
};
