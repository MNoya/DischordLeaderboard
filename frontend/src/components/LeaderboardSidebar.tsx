import { Link } from "react-router-dom";
import { BsAsterisk, BsPaletteFill, ExternalLink } from "./Icons";

import { Trophy } from "./Brand";
import { Pips } from "./ManaPips";
import { SectionLabel } from "./SectionLabel";
import { SurfaceCard } from "./SurfaceCard";
import { TrophyCount } from "./TrophyCount";
import { Record } from "./Record";

import { useColorsSummary, useFormatScopedTrophies, useRecentTrophies } from "../data/hooks";
import { lcqDraft2Earnings } from "../data/scoring";
import { formatsForBucket } from "../data/format-buckets";
import { colorsOf, effectiveColorCount, mainColors, playerPath, relativeTime } from "../data/utils";
import { FMT_COLORS, FMT_DEFAULT_COLOR, shortFormat } from "../data/format-display";
import { colorsDisplayName, MULTI, OTHER } from "../data/filters";
import { guildLogoTransform, guildSvgUrl } from "../data/guild-art";
import type { ColorsSummary, RecentTrophy } from "../types/leaderboard";

// Derive a Top Colors summary from a list of trophy events. Each trophy is
// bucketed into MULTI (≥4 effective colors) or its main archetype (splash
// stripped). Used for the format-scoped sidebar where no precomputed per-format
// summary view exists. LCQ Day 2 runs count their cash payout; a paying run
// without a trophy still enters the table on cash alone.
function topColorsFromTrophies(setCode: string, trophies: RecentTrophy[]): ColorsSummary[] {
  const counts = new Map<string, { trophies: number; earnings: number; players: Set<string> }>();
  for (const t of trophies) {
    const isTrophy = t.isTrophy !== false;
    const cash = lcqCashForRow(t);
    if (!isTrophy && cash === 0) continue;
    const keys: string[] = [];
    const main = colorsOf(t.colors);
    if (main) keys.push(main);
    if (effectiveColorCount(t.colors) >= 4) keys.push(MULTI);
    for (const key of keys) {
      const cur = counts.get(key) ?? { trophies: 0, earnings: 0, players: new Set<string>() };
      if (isTrophy) cur.trophies += 1;
      cur.earnings += cash;
      cur.players.add(t.slug);
      counts.set(key, cur);
    }
  }
  return [...counts.entries()]
    .map(([colors, v]) => ({
      setCode,
      colors,
      trophies: v.trophies,
      events: v.trophies,
      players: v.players.size,
      earnings: v.earnings,
    }))
    .sort((a, b) => b.trophies - a.trophies || b.earnings - a.earnings);
}

const LCQ_DRAFT_2_FORMATS = formatsForBucket("LCQ Draft 2");

function lcqCashForRow(t: RecentTrophy): number {
  return LCQ_DRAFT_2_FORMATS.includes(t.format) ? lcqDraft2Earnings(t.wins) : 0;
}

export function LeaderboardSidebar({
  setCode,
  colors = "ALL",
  format = "ALL",
  otherCombos = [],
  onColorsSelect,
  searchParams,
  stats,
}: {
  setCode: string;
  colors?: string;
  format?: string;
  otherCombos?: string[];
  onColorsSelect?: (code: string) => void;
  searchParams?: URLSearchParams;
  stats?: { players: number; events: string; updated: string };
}) {
  const qs = searchParams?.toString() ?? "";
  const colorsScoped = colors !== "ALL";
  const formatScoped = !colorsScoped && format !== "ALL";

  const { data: topColorsAll } = useColorsSummary(formatScoped ? undefined : setCode);
  const { data: formatTrophies } = useFormatScopedTrophies(
    formatScoped ? setCode : undefined,
    formatScoped ? format : undefined,
  );
  const { data: recentAll } = useRecentTrophies(
    formatScoped ? undefined : setCode,
    colorsScoped ? 100 : 10,
  );

  const topColors: ColorsSummary[] | undefined = formatScoped
    ? formatTrophies && topColorsFromTrophies(setCode, formatTrophies)
    : topColorsAll?.filter((r) => r.trophies > 0);

  const recentSource: RecentTrophy[] | undefined = formatScoped ? formatTrophies : recentAll;
  const recentScoped = !colorsScoped
    ? (recentSource ? recentSource.slice(0, 10) : undefined)
    : (recentSource ?? [])
        .filter((t) => {
          if (colors === MULTI) return effectiveColorCount(t.colors) >= 4;
          if (colors === OTHER) return otherCombos.includes(colorsOf(t.colors));
          return colorsOf(t.colors) === colors;
        })
        .slice(0, 10);

  const scopeLabel = colorsScoped
    ? colorsDisplayName(colors)
    : formatScoped
      ? shortFormat(format)
      : "";
  const scoped = colorsScoped || formatScoped;
  const formatColor = formatScoped ? (FMT_COLORS[format] ?? FMT_DEFAULT_COLOR) : null;
  const scopeChip = colorsScoped ? (
    <span className="text-green">{scopeLabel}</span>
  ) : formatScoped ? (
    <span style={{ color: formatColor! }}>{scopeLabel}</span>
  ) : null;
  const lcqScope = formatScoped && format === "LCQ";
  const recentNoun = lcqScope ? "TROPHIES & DAY 2" : "TROPHIES";
  const recentTitle = scoped ? <>RECENT {scopeChip} {recentNoun}</> : "RECENT TROPHIES";
  const recentEmpty = scoped ? `NO RECENT ${scopeLabel} ${recentNoun}` : "NO TROPHIES YET";
  const topColorsTitle = formatScoped
    ? <>TOP COLORS · {scopeChip} {lcqScope ? "TROPHIES & CASH" : "TROPHIES"}</>
    : "TOP COLORS · BY TROPHIES";
  // Pips per row only when the scope mixes combos (unscoped, format-only, OTHER, SOUP).
  // For a fixed named combo every row has the same colors — promote the pips
  // to the section title and free up width for the player name.
  const namedScope = colorsScoped && colors !== MULTI && colors !== OTHER;
  const showRowPips = !namedScope;

  return (
    <aside className="flex flex-col gap-4">
      <SurfaceCard>
        <SectionLabel
          size={16}
          letterSpacing={lcqScope ? "0.14em" : undefined}
          className="mb-1 text-subtle whitespace-nowrap"
        >
          {topColorsTitle}
        </SectionLabel>
        {!topColors ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : topColors.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">NO TROPHIES YET</div>
        ) : (
          topColors.slice(0, 5).map((row, i) => {
            const isActive = row.colors === colors;
            const cls =
              (lcqScope
                ? "grid grid-cols-[24px_28px_1fr_auto_auto] "
                : "grid grid-cols-[24px_28px_1fr_auto] ") +
              "gap-2 items-center py-2 -mx-1 px-1 text-left transition-colors " +
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
                <span className="font-display text-[14px] tracking-[0.05em] pl-1.5">
                  {colorsDisplayName(row.colors)}
                </span>
                {lcqScope && (
                  <span className="font-display text-[14px] tracking-[0.02em] tabular-nums text-right text-green mr-2">
                    {row.earnings ? `$${row.earnings / 1000}K` : ""}
                  </span>
                )}
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
        <div className="mb-1 flex items-center gap-1.5">
          <Trophy size={16} color="#ffc63a" />
          <SectionLabel size={16} className="text-subtle">{recentTitle}</SectionLabel>
          {namedScope && (
            <span className="ml-auto inline-flex items-center">
              <Pips colors={colors} size={12} />
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
              "group grid gap-2 items-center py-[7px] no-underline text-inherit transition-colors hover:bg-surface2 -mx-1 px-1 " +
              (showRowPips
                ? "grid-cols-[auto_1fr_28px_96px] "
                : "grid-cols-[1fr_28px_96px] ") +
              (i ? "border-t border-border" : "");
            const inner = (
              <>
                {showRowPips && (
                  effectiveColorCount(t.colors) >= 4
                    ? (
                      <span className="inline-flex items-center gap-px shrink-0">
                        <Pips colors={mainColors(t.colors).slice(0, 3)} size={10} />
                        <BsPaletteFill size={12} aria-hidden="true" />
                      </span>
                    )
                    : <Pips colors={t.colors} size={10} />
                )}
                <span className="font-display text-[15px] leading-none tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis min-w-0">
                  {t.displayName.toUpperCase()}
                </span>
                <Record
                  wins={t.wins}
                  losses={t.losses}
                  mono
                  color={lcqCashForRow(t) > 0 ? "#2ee85c" : undefined}
                  className="mono text-[13px] text-subtle text-right"
                />
                <span className="grid grid-cols-[1fr_auto] items-center gap-1 mono text-dim">
                  <span
                    className="text-[11px] text-text justify-self-center"
                    style={LCQ_DRAFT_2_FORMATS.includes(t.format) ? { color: FMT_COLORS.LCQ } : undefined}
                  >
                    {shortFormat(t.format)}
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="text-[11px] tabular-nums transition-colors group-hover:text-text">
                      {relativeTime(t.finishedAt)}
                    </span>
                    {isExternal && (
                      <ExternalLink size={13} className="transition-colors group-hover:text-text" aria-hidden="true" />
                    )}
                  </span>
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
                to={{ pathname: playerPath(t.slug, setCode), search: qs }}
                className={cls}
              >
                {inner}
              </Link>
            );
          })
        )}
      </SurfaceCard>
      {stats && (
        <div className="mono text-[11px] text-muted text-right -mt-2">
          {stats.players} PLAYERS · {stats.events} EVENTS · UPDATED {stats.updated}
        </div>
      )}
    </aside>
  );
}
