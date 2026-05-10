import { Link } from "react-router-dom";
import { BsAsterisk, BsPaletteFill } from "react-icons/bs";
import { ExternalLink } from "lucide-react";

import { Trophy } from "./Brand";
import { Pips } from "./ManaPips";
import { SectionLabel } from "./SectionLabel";
import { SurfaceCard } from "./SurfaceCard";
import { TrophyCount } from "./TrophyCount";
import { Record } from "./Record";

import { useColorsSummary, useRecentTrophies } from "../data/hooks";
import { colorsOf, effectiveColorCount, relativeTime, shortFormatLabel } from "../data/utils";
import { colorsDisplayName, MULTI, OTHER } from "../data/filters";

export function LeaderboardSidebar({
  setCode,
  colors = "ALL",
  otherCombos = [],
  onColorsSelect,
  searchParams,
}: {
  setCode: string;
  colors?: string;
  otherCombos?: string[];
  onColorsSelect?: (code: string) => void;
  searchParams?: URLSearchParams;
}) {
  const qs = searchParams?.toString() ?? "";
  const scoped = colors !== "ALL";
  const { data: topColors } = useColorsSummary(setCode);
  const { data: recent } = useRecentTrophies(setCode, scoped ? 100 : 5);
  const recentScoped = !scoped
    ? recent
    : (recent ?? [])
        .filter((t) => {
          if (colors === MULTI) return effectiveColorCount(t.colors) >= 4;
          if (colors === OTHER) {
            if (effectiveColorCount(t.colors) >= 4) return false;
            return otherCombos.includes(colorsOf(t.colors));
          }
          return colorsOf(t.colors) === colors;
        })
        .slice(0, 5);

  const scopeLabel = colorsDisplayName(colors);
  const recentTitle = scoped ? `RECENT ${scopeLabel} TROPHIES` : "RECENT TROPHIES";
  const recentEmpty = scoped ? `NO RECENT ${scopeLabel} TROPHIES` : "NO TROPHIES YET";
  // Pips per row only when the scope mixes combos (unscoped, OTHER, SOUP).
  // For a fixed named combo every row has the same colors — promote the pips
  // to the section title and free up width for the player name.
  const namedScope = scoped && colors !== MULTI && colors !== OTHER;
  const showRowPips = !namedScope;

  return (
    <aside className="flex flex-col gap-4">
      <SurfaceCard>
        <SectionLabel size={13} className="mb-2.5 text-subtle">TOP COLORS · BY TROPHIES</SectionLabel>
        {!topColors ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : topColors.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">NO TROPHIES YET</div>
        ) : (
          topColors.slice(0, 5).map((row, i) => {
            const isActive = row.colors === colors;
            const cls =
              "grid grid-cols-[24px_28px_1fr_auto] gap-2 items-center py-2 -mx-1 px-1 rounded text-left transition-colors " +
              (i ? "border-t border-border" : "") +
              (isActive ? " text-green" : "") +
              (onColorsSelect ? " cursor-pointer hover:bg-surface2" : "");
            const inner = (
              <>
                <span className="mono text-[11px] text-muted">{i + 1}</span>
                <span className="flex justify-center">
                  {row.colors === MULTI ? (
                    <BsPaletteFill size={18} className="shrink-0 block -my-1" aria-hidden="true" />
                  ) : (
                    <Pips colors={row.colors} size={12} />
                  )}
                </span>
                <span className="font-display text-[14px] tracking-[0.05em]">
                  {colorsDisplayName(row.colors)}
                </span>
                <TrophyCount count={row.trophies} size="compact" className="text-muted" />
              </>
            );
            return onColorsSelect ? (
              <button
                key={row.colors}
                type="button"
                onClick={() => onColorsSelect(isActive ? "ALL" : row.colors)}
                aria-pressed={isActive}
                className={cls + " bg-transparent border-0 w-full"}
              >
                {inner}
              </button>
            ) : (
              <div key={row.colors} className={cls}>
                {inner}
              </div>
            );
          })
        )}
      </SurfaceCard>

      <SurfaceCard>
        <div className="mb-2.5 flex items-center gap-1.5">
          <Trophy size={13} color="#ffc63a" />
          <SectionLabel size={13} className="text-subtle">{recentTitle}</SectionLabel>
          {namedScope && (
            <span className="ml-auto inline-flex items-center">
              <Pips colors={colors} size={13} />
            </span>
          )}
          {colors === MULTI && <BsPaletteFill size={13} className="ml-auto" aria-hidden="true" />}
          {colors === OTHER && <BsAsterisk size={12} className="ml-auto" aria-hidden="true" />}
        </div>
        {!recentScoped ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : recentScoped.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">{recentEmpty}</div>
        ) : (
          recentScoped.map((t, i) => {
            const isExternal = Boolean(t.seventeenlandsEventId);
            const cls =
              "grid gap-2 items-center py-[7px] no-underline text-inherit transition-colors hover:bg-surface2 -mx-1 px-1 " +
              (showRowPips
                ? "grid-cols-[auto_1fr_30px_28px_24px_12px] "
                : "grid-cols-[1fr_30px_28px_24px_12px] ") +
              (i ? "border-t border-border" : "");
            const inner = (
              <>
                {showRowPips && <Pips colors={colorsOf(t.colors)} size={10} />}
                <span className="font-display text-[15px] leading-none tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis min-w-0">
                  {t.displayName.toUpperCase()}
                </span>
                <Record
                  wins={t.wins}
                  losses={t.losses}
                  mono
                  className="mono text-[10px] text-subtle text-right"
                />
                <span className="mono text-[10px] text-dim">{shortFormatLabel(t.format)}</span>
                <span className="mono text-[10px] text-dim text-right">{relativeTime(t.finishedAt)}</span>
                <span className="flex justify-center text-dim">
                  {isExternal && <ExternalLink size={10} aria-hidden="true" />}
                </span>
              </>
            );
            const key = `${t.slug}-${t.finishedAt}`;
            return isExternal ? (
              <a
                key={key}
                href={`https://www.17lands.com/deck/${t.seventeenlandsEventId}`}
                target="_blank"
                rel="noopener noreferrer"
                className={cls}
              >
                {inner}
              </a>
            ) : (
              <Link
                key={key}
                to={{ pathname: `/${setCode}/player/${t.slug}`, search: qs }}
                className={cls}
              >
                {inner}
              </Link>
            );
          })
        )}
      </SurfaceCard>
    </aside>
  );
}
