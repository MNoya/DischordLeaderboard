import type { ReactNode } from "react";
import { CommunityGrid } from "./CommunityGrid";
import { FullBreakdownList } from "./FullBreakdownList";
import type { Card, P0P1PickStat } from "../../types/p0p1";

export function PostVotingStats({
  pickStats,
  cardsByName,
  picksBySlot,
  yourPicks,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  picksBySlot?: Map<string, string>;
  yourPicks?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 lg:gap-6">
      <CommunityGrid pickStats={pickStats} cardsByName={cardsByName} picksBySlot={picksBySlot} />
      {yourPicks}
      <FullBreakdownList pickStats={pickStats} cardsByName={cardsByName} picksBySlot={picksBySlot} />
    </div>
  );
}
