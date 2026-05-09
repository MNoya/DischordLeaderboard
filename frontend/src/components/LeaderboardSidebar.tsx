import { Link } from "react-router-dom";

import { Trophy } from "./Brand";
import { Pips } from "./ManaPips";
import { SectionLabel } from "./SectionLabel";
import { SurfaceCard } from "./SurfaceCard";
import { TrophyCount } from "./TrophyCount";
import { Record } from "./Record";

import { useRecentTrophies } from "../data/hooks";
import { archetypeOf, relativeTime, shortFormatLabel } from "../data/utils";
import { ARCHETYPE_NAMES } from "../data/filters";

// Sidebar — desktop right rail. Two cards: top archetypes by trophies, recent
// trophies. The recent-trophies feed is fetched live from
// `public_recent_trophies` (or the fixture equivalent today).
//
// Top archetypes is still synthesised since there's no `public_archetype_summary`
// view yet — it's a 4-row hand-curated list per set until that ships.

export function LeaderboardSidebar({ setCode }: { setCode: string }) {
  // Snapshot — until backend exposes a per-set archetype rollup, this is a
  // hand-curated guess at the metagame's heaviest decks for SOS.
  const topArchetypes: Array<[string, number]> = [
    ["WR", 18],
    ["UR", 14],
    ["BG", 12],
    ["WU", 10],
    ["RG", 8],
  ];

  const { data: recent } = useRecentTrophies(setCode, 5);

  return (
    <aside className="flex flex-col gap-4">
      <SurfaceCard>
        <SectionLabel className="mb-2.5">TOP ARCHETYPES · BY TROPHIES</SectionLabel>
        {topArchetypes.map(([code, trophies], i) => (
          <div
            key={code}
            className={
              "grid grid-cols-[24px_auto_1fr_auto] gap-2 items-center py-2 " +
              (i ? "border-t border-border" : "")
            }
          >
            <span className="mono text-[11px] text-muted">{i + 1}</span>
            <Pips colors={code} size={12} />
            <span className="font-display text-[14px] tracking-[0.05em]">
              {ARCHETYPE_NAMES[code] ?? code}
            </span>
            <TrophyCount count={trophies} size="compact" className="text-muted" />
          </div>
        ))}
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
