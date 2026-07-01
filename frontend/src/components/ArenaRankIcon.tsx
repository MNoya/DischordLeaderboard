import type { PlayerDraftEvent } from "../types/leaderboard";

const TIER_FILE_PREFIX: Record<string, string> = {
  Bronze: "bronze",
  Silver: "silver",
  Gold: "gold",
  Platinum: "plat",
  Diamond: "diamond",
};

// 17lands rank strings are "<Tier>-<division>" ("Gold-3"); Mythic has no meaningful
// division. Junk values ("0-1", "None-2") parse to null and render nothing.
export function parseArenaRank(endRank: string | null | undefined): { label: string; file: string } | null {
  if (!endRank) {
    return null;
  }
  const [tier, division] = endRank.split("-");
  if (tier === "Mythic") {
    return { label: "Mythic", file: "mythic" };
  }
  const prefix = TIER_FILE_PREFIX[tier];
  const div = Number(division);
  if (!prefix || !(div >= 1 && div <= 4)) {
    return null;
  }
  return { label: `${tier} ${div}`, file: `${prefix}${div}` };
}

export function latestArenaRank(events: PlayerDraftEvent[]): string | null {
  for (const event of events) {
    if (parseArenaRank(event.endRank)) {
      return event.endRank ?? null;
    }
  }
  return null;
}

export function ArenaRankIcon({
  endRank,
  size = 24,
  title,
  className,
}: {
  endRank: string | null | undefined;
  size?: number;
  title?: string;
  className?: string;
}) {
  const parsed = parseArenaRank(endRank);
  if (!parsed) {
    return null;
  }
  return (
    <img
      src={`${import.meta.env.BASE_URL}rank/${parsed.file}.png`}
      alt={parsed.label}
      title={title ?? parsed.label}
      className={className}
      style={{ height: size, width: "auto" }}
    />
  );
}
