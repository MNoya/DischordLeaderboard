import { CommunityGrid } from "./CommunityGrid";
import { FullBreakdownList } from "./FullBreakdownList";
import type { Card, P0P1PickStat } from "../../types/p0p1";

export function PostVotingStats({
  pickStats,
  cardsByName,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  return (
    <div className="flex flex-col gap-6">
      <CommunityGrid pickStats={pickStats} cardsByName={cardsByName} />
      <FullBreakdownList pickStats={pickStats} cardsByName={cardsByName} />
    </div>
  );
}
