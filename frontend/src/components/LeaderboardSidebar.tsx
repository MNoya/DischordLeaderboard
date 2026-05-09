import { Link } from "react-router-dom";

import { Trophy } from "./Brand";
import { Pips } from "./ManaPips";
import { SectionLabel } from "./SectionLabel";
import { SurfaceCard } from "./SurfaceCard";
import { TrophyCount } from "./TrophyCount";
import { Record } from "./Record";

import { useArchetypeSummary, useRecentTrophies } from "../data/hooks";
import { archetypeOf, relativeTime, shortFormatLabel } from "../data/utils";
import { ARCHETYPE_NAMES } from "../data/filters";

// Sidebar — desktop right rail. Two cards: top archetypes by trophies, recent
// trophies. Both feeds are now real:
//   - top archetypes aggregates public_archetype_leaderboard server-side
//   - recent trophies from public_recent_trophies

export function LeaderboardSidebar({ setCode }: { setCode: string }) {
  const { data: topArchetypes } = useArchetypeSummary(setCode);
  const { data: recent } = useRecentTrophies(setCode, 5);

  return (
    <aside className="flex flex-col gap-4">
      <SurfaceCard>
        <SectionLabel className="mb-2.5">TOP ARCHETYPES · BY TROPHIES</SectionLabel>
        {!topArchetypes ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : topArchetypes.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">NO TROPHIES YET</div>
        ) : (
          topArchetypes.slice(0, 5).map((row, i) => (
            <div
              key={row.archetype}
              className={
                "grid grid-cols-[24px_auto_1fr_auto] gap-2 items-center py-2 " +
                (i ? "border-t border-border" : "")
              }
            >
              <span className="mono text-[11px] text-muted">{i + 1}</span>
              <Pips colors={row.archetype} size={12} />
              <span className="font-display text-[14px] tracking-[0.05em]">
                {ARCHETYPE_NAMES[row.archetype] ?? row.archetype}
              </span>
              <TrophyCount count={row.trophies} size="compact" className="text-muted" />
            </div>
          ))
        )}
      </SurfaceCard>

      <SurfaceCard>
        <SectionLabel className="mb-2.5">RECENT TROPHIES</SectionLabel>
        {!recent ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : recent.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">NO TROPHIES YET</div>
        ) : (
          recent.map((t, i) => (
            <Link
              key={`${t.slug}-${t.finishedAt}`}
              to={`/${setCode}/player/${t.slug}`}
              className={
                "grid grid-cols-[auto_1fr_auto_auto] gap-2 items-center py-[7px] no-underline transition-colors hover:bg-surface2 -mx-1 px-1 " +
                (i ? "border-t border-border" : "")
              }
            >
              <Trophy size={14} color="#ffc63a" />
              <div className="flex items-center gap-1.5 min-w-0">
                <Pips colors={archetypeOf(t.colors)} size={10} />
                <span className="font-display text-[13px] tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis">
                  {t.displayName.toUpperCase()}
                </span>
              </div>
              <span className="mono text-[10px] text-muted">
                <Record wins={t.wins} losses={t.losses} mono />
                <span className="text-dim ml-1">{shortFormatLabel(t.format)}</span>
              </span>
              <span className="mono text-[10px] text-dim">{relativeTime(t.finishedAt)}</span>
            </Link>
          ))
        )}
      </SurfaceCard>
    </aside>
  );
}
