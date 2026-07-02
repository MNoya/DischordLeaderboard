// Pure scoring and comparison functions for the P0P1 results phases.
// All computation happens client-side from the ratings JSON + pick stats/ballots.

import type { Card, P0P1PickStat, SlotKey } from "../types/p0p1";
import type { SlotDefinition } from "../types/p0p1";

export type P0P1Phase = "voting" | "postVoting" | "midway" | "finalizing" | "final";

export interface CardRating {
  card_name: string;
  // null means 17lands had no data for this card
  gihwr: number | null;
  gih: number;
}

export interface RatingsSnapshot {
  setCode: string;
  phase: "midway" | "final" | null;
  dateRange: { start: string; end: string } | null;
  cards: CardRating[];
}

export interface TeamPick {
  slot: SlotKey;
  cardName: string;
  gihwr: number;
}

export interface TeamResult {
  picks: TeamPick[];
  score: number;
}

// Cards with fewer than this many GIH games are excluded from scoring and team-building
export const GIH_SAMPLE_FLOOR = 500;

export function buildRatingsByName(snapshot: RatingsSnapshot): Map<string, CardRating> {
  return new Map(snapshot.cards.map((c) => [c.card_name, c]));
}

// Sum GIHWR for a ballot. Cards absent from ratings, below the GIH floor,
// or with null gihwr contribute 0 (missing slots already contribute 0 via omission).
export function scoreBallot(
  picks: Map<SlotKey, string>,
  ratingsByName: Map<string, CardRating>,
): number {
  let total = 0;
  for (const cardName of picks.values()) {
    const rating = ratingsByName.get(cardName);
    if (!rating || rating.gih < GIH_SAMPLE_FLOOR || rating.gihwr === null) continue;
    total += rating.gihwr * 100;
  }
  return total;
}

// Best-possible legal team: max-weight assignment of cards to slots under the
// uniqueness constraint. Uses most-constrained-first greedy, which is optimal
// for the MSH slot structure because the 5 color-common slots have disjoint
// card pools and the wildcard slots are naturally last.
export function bestPossibleTeam(
  cards: Card[],
  slots: SlotDefinition[],
  ratingsByName: Map<string, CardRating>,
): TeamResult {
  const empty = new Set<string>();

  // For each slot, collect above-floor eligible cards sorted by GIHWR desc
  const slotCandidates: Array<Array<{ name: string; gihwr: number }>> = slots.map((slot) =>
    cards
      .filter((c) => slot.filter(c, empty))
      .flatMap((c) => {
        const r = ratingsByName.get(c.name);
        if (!r || r.gih < GIH_SAMPLE_FLOOR || r.gihwr === null) return [];
        return [{ name: c.name, gihwr: r.gihwr }];
      })
      .sort((a, b) => b.gihwr - a.gihwr),
  );

  // Process most-constrained slots first (fewest eligible cards)
  const slotOrder = slots
    .map((_, i) => i)
    .sort((a, b) => slotCandidates[a].length - slotCandidates[b].length);

  const assigned = new Map<number, { name: string; gihwr: number }>();
  const usedCards = new Set<string>();

  for (const idx of slotOrder) {
    for (const card of slotCandidates[idx]) {
      if (!usedCards.has(card.name)) {
        assigned.set(idx, card);
        usedCards.add(card.name);
        break;
      }
    }
  }

  const picks: TeamPick[] = slots.map((slot, i) => {
    const card = assigned.get(i);
    return { slot: slot.key, cardName: card?.name ?? "", gihwr: card?.gihwr ?? 0 };
  });

  return { picks, score: picks.reduce((sum, p) => sum + p.gihwr * 100, 0) };
}

// Most-popular legal team: same uniqueness constraint, greedy from most-voted
// card per slot. SLOTS order (color slots before wildcards) is intentional so
// the specific slots claim their top card before wildcards pick remainders.
export function mostPopularTeam(
  pickStats: P0P1PickStat[],
  slots: SlotDefinition[],
  ratingsByName: Map<string, CardRating>,
): TeamResult {
  const statsBySlot = new Map<SlotKey, P0P1PickStat[]>();
  for (const stat of pickStats) {
    const arr = statsBySlot.get(stat.slot) ?? [];
    arr.push(stat);
    statsBySlot.set(stat.slot, arr);
  }

  const usedCards = new Set<string>();
  const picks: TeamPick[] = [];

  for (const slot of slots) {
    const candidates = (statsBySlot.get(slot.key) ?? []).sort(
      (a, b) => b.pickCount - a.pickCount,
    );
    let picked: TeamPick = { slot: slot.key, cardName: "", gihwr: 0 };
    for (const stat of candidates) {
      if (!usedCards.has(stat.cardName)) {
        usedCards.add(stat.cardName);
        const r = ratingsByName.get(stat.cardName);
        picked = {
          slot: slot.key,
          cardName: stat.cardName,
          gihwr: r && r.gih >= GIH_SAMPLE_FLOOR && r.gihwr !== null ? r.gihwr : 0,
        };
        break;
      }
    }
    picks.push(picked);
  }

  return { picks, score: picks.reduce((sum, p) => sum + p.gihwr * 100, 0) };
}

// ── Midway versus card ──────────────────────────────────────────────────────

export interface MidwayVersusSide {
  name: string;
  imageUrl: string;
  // null when below the GIH floor or absent from ratings
  gihwr: number | null;
  gih: number;
}

export interface MidwaySlotVersus {
  slotKey: SlotKey;
  slotLabel: string;
  // null when logged-out or user left this slot empty
  yours: MidwayVersusSide | null;
  crowd: MidwayVersusSide;
  best: MidwayVersusSide;
}

function makeSide(
  cardName: string,
  ratingsByName: Map<string, CardRating>,
  cardsByName: Map<string, Card>,
): MidwayVersusSide {
  const r = ratingsByName.get(cardName);
  const gihwr = r && r.gih >= GIH_SAMPLE_FLOOR && r.gihwr !== null ? r.gihwr : null;
  return {
    name: cardName,
    imageUrl: cardsByName.get(cardName)?.imageNormal ?? "",
    gihwr,
    gih: r?.gih ?? 0,
  };
}

export function buildMidwaySlotVersus(
  slots: SlotDefinition[],
  picksBySlot: Map<string, string>,
  crowdTeam: TeamResult,
  bestTeam: TeamResult,
  ratingsByName: Map<string, CardRating>,
  cardsByName: Map<string, Card>,
  includeYours: boolean,
): MidwaySlotVersus[] {
  const crowdBySlot = new Map(crowdTeam.picks.map((p) => [p.slot, p]));
  const bestBySlot = new Map(bestTeam.picks.map((p) => [p.slot, p]));

  return slots.map((slot) => {
    const yourCardName = includeYours ? picksBySlot.get(slot.key) : undefined;
    const crowdCardName = crowdBySlot.get(slot.key)?.cardName ?? "";
    const bestCardName = bestBySlot.get(slot.key)?.cardName ?? "";

    return {
      slotKey: slot.key,
      slotLabel: slot.label,
      yours: yourCardName ? makeSide(yourCardName, ratingsByName, cardsByName) : null,
      crowd: makeSide(crowdCardName, ratingsByName, cardsByName),
      best: makeSide(bestCardName, ratingsByName, cardsByName),
    };
  });
}

// ── Rank all ballots by summed GIHWR (descending). ────────────────────────── Partial ballots sink naturally.
// Returns the same ballots array with rank and percentile attached.
export interface RankedBallot {
  ballotId: number;
  name: string;
  avatarUrl: string | null;
  picks: Map<SlotKey, string>;
  score: number;
  rank: number;
  percentile: number;
}

export function rankBallots(
  ballots: Array<{ ballotId: number; name: string; avatarUrl: string | null; picks: Map<SlotKey, string> }>,
  ratingsByName: Map<string, CardRating>,
): RankedBallot[] {
  const scored = ballots.map((b) => ({
    ...b,
    score: scoreBallot(b.picks, ratingsByName),
    rank: 0,
    percentile: 0,
  }));
  scored.sort((a, b) => b.score - a.score);
  const n = scored.length;
  for (let i = 0; i < n; i++) {
    scored[i].rank = i + 1;
    // percentile: what fraction scored strictly worse
    scored[i].percentile = n > 1 ? Math.round(((n - i - 1) / (n - 1)) * 100) : 100;
  }
  return scored;
}

export interface SlotRankGap {
  slot: SlotKey;
  slotLabel: string;
  cardName: string;
  popularityRank: number;
  gihwrRank: number;
  gap: number;
  kind: "overrated" | "underrated";
}

// Per-slot rank gap for the highlights reel.
// Overrated: high popularity rank, low GIHWR rank (everyone took it; it underperforms).
// Underrated: low popularity rank, high GIHWR rank (nobody took it; it's secretly strong).
// Returns top highlights sorted by |gap| descending.
export function slotRankGaps(
  pickStats: P0P1PickStat[],
  slots: SlotDefinition[],
  ratingsByName: Map<string, CardRating>,
  topN = 3,
): SlotRankGap[] {
  const slotLabelMap = new Map(slots.map((s) => [s.key, s.label]));
  const bySlot = new Map<SlotKey, P0P1PickStat[]>();
  for (const stat of pickStats) {
    const arr = bySlot.get(stat.slot) ?? [];
    arr.push(stat);
    bySlot.set(stat.slot, arr);
  }

  const gaps: SlotRankGap[] = [];

  for (const [slotKey, stats] of bySlot) {
    // Sort by popularity to get popularity ranks
    const byPop = [...stats].sort((a, b) => b.pickCount - a.pickCount);
    // Sort by GIHWR to get GIHWR ranks (among above-floor cards only)
    const byGihwr = [...stats]
      .filter((s) => {
        const r = ratingsByName.get(s.cardName);
        return r && r.gih >= GIH_SAMPLE_FLOOR && r.gihwr !== null;
      })
      .sort((a, b) => {
        const ra = ratingsByName.get(a.cardName)!.gihwr!;
        const rb = ratingsByName.get(b.cardName)!.gihwr!;
        return rb - ra;
      });

    for (let popIdx = 0; popIdx < byPop.length; popIdx++) {
      const stat = byPop[popIdx];
      const rating = ratingsByName.get(stat.cardName);
      if (!rating || rating.gih < GIH_SAMPLE_FLOOR || rating.gihwr === null) continue;
      const gihwrIdx = byGihwr.findIndex((s) => s.cardName === stat.cardName);
      if (gihwrIdx === -1) continue;
      const gap = popIdx - gihwrIdx; // positive = overrated, negative = underrated
      if (gap === 0) continue;
      gaps.push({
        slot: slotKey,
        slotLabel: slotLabelMap.get(slotKey) ?? slotKey,
        cardName: stat.cardName,
        popularityRank: popIdx + 1,
        gihwrRank: gihwrIdx + 1,
        gap,
        kind: gap > 0 ? "overrated" : "underrated",
      });
    }
  }

  return gaps
    .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap))
    .slice(0, topN);
}
