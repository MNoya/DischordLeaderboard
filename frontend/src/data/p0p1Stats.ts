import type { P0P1PickStat, SlotKey } from "../types/p0p1";

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

export function findExtremes(slotStats: P0P1PickStat[]): { most: P0P1PickStat[]; least: P0P1PickStat[] } {
  if (slotStats.length === 0) return { most: [], least: [] };
  const maxCount = Math.max(...slotStats.map((s) => s.pickCount));
  const minCount = Math.min(...slotStats.map((s) => s.pickCount));
  return {
    most: slotStats.filter((s) => s.pickCount === maxCount),
    least: slotStats.filter((s) => s.pickCount === minCount),
  };
}

export function globalRanked(stats: P0P1PickStat[]): P0P1PickStat[] {
  return [...stats].sort((a, b) => b.pickCount - a.pickCount);
}

export type PickClassification = {
  state: "most" | "minority" | "rogue";
  qualifier: string;
};

export function classifyYourPick(
  yourStat: P0P1PickStat,
  most: P0P1PickStat[],
  least: P0P1PickStat[],
): PickClassification {
  const inMost = most.some((s) => s.cardName === yourStat.cardName);
  if (inMost) {
    return most.length > 1
      ? { state: "most", qualifier: "TIED FOR MOST PICKED" }
      : { state: "most", qualifier: "MOST PICKED" };
  }
  const inLeast = least.some((s) => s.cardName === yourStat.cardName);
  if (inLeast) {
    return { state: "rogue", qualifier: "ROGUE PICK" };
  }
  return { state: "minority", qualifier: "MINORITY PICK" };
}
