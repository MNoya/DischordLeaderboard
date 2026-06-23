import type { Card, P0P1PickStat, PickVersus, PickVersusSide, SlotKey } from "../types/p0p1";

export function groupBySlot(stats: P0P1PickStat[]): Map<SlotKey, P0P1PickStat[]> {
  const map = new Map<SlotKey, P0P1PickStat[]>();
  for (const stat of stats) {
    const slotStats = map.get(stat.slot);
    if (slotStats) {
      slotStats.push(stat);
    } else {
      map.set(stat.slot, [stat]);
    }
  }
  return map;
}

const ROGUE_VOTE_LENIENCY = 2;

export function findExtremes(slotStats: P0P1PickStat[]): { most: P0P1PickStat[]; least: P0P1PickStat[] } {
  if (slotStats.length === 0) return { most: [], least: [] };
  const maxCount = Math.max(...slotStats.map((s) => s.pickCount));
  const minCount = Math.min(...slotStats.map((s) => s.pickCount));
  return {
    most: slotStats.filter((s) => s.pickCount === maxCount),
    least: slotStats.filter((s) => s.pickCount <= minCount + ROGUE_VOTE_LENIENCY),
  };
}

export function pickPctLabel(pickPct: number): string {
  return `${Math.max(Math.round(pickPct), 1)}%`;
}

export function participantCount(stats: P0P1PickStat[]): number {
  const totalsPerSlot = new Map<SlotKey, number>();
  for (const s of stats) {
    totalsPerSlot.set(s.slot, (totalsPerSlot.get(s.slot) ?? 0) + s.pickCount);
  }
  if (totalsPerSlot.size === 0) return 0;
  return Math.max(...totalsPerSlot.values());
}

export type PickClassification = {
  state: "most" | "minority" | "rogue";
  qualifier?: string;
};

export function classifyYourPick(
  yourStat: P0P1PickStat,
  most: P0P1PickStat[],
  least: P0P1PickStat[],
): PickClassification {
  const inMost = most.some((s) => s.cardName === yourStat.cardName);
  if (inMost) {
    return most.length > 1
      ? { state: "most", qualifier: "TIED FOR CROWD FAVORITE" }
      : { state: "most", qualifier: "CROWD FAVORITE" };
  }
  const inLeast = least.some((s) => s.cardName === yourStat.cardName);
  if (inLeast) {
    return { state: "rogue", qualifier: "ROGUE PICK" };
  }
  return { state: "minority" };
}

export function buildPickVersus(
  slotStats: P0P1PickStat[],
  yourCardName: string,
  cardsByName: Map<string, Card>,
  slotKey: SlotKey,
  slotLabel: string,
): PickVersus | null {
  if (slotStats.length === 0) return null;
  const yourStat = slotStats.find((s) => s.cardName === yourCardName);
  if (!yourStat) return null;
  const { most, least } = findExtremes(slotStats);
  const crowdStat = most[0];
  if (!crowdStat) return null;

  const classification = classifyYourPick(yourStat, most, least);
  return {
    slotKey,
    slotLabel,
    state: classification.state === "most" ? "matched" : classification.state,
    agreed: classification.state === "most",
    tiedCount: most.length,
    crowd: sideFromStat(crowdStat, cardsByName),
    yours: sideFromStat(yourStat, cardsByName),
  };
}

function sideFromStat(stat: P0P1PickStat, cardsByName: Map<string, Card>): PickVersusSide {
  const card = cardsByName.get(stat.cardName);
  return { name: stat.cardName, imageUrl: card?.imageNormal ?? "", pickPct: stat.pickPct };
}
