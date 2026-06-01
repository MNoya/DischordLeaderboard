import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronUp } from "lucide-react";
import { AAvatar, Trophy, fmtPts } from "./Brand";
import { Record } from "./Record";
import { ErrorState } from "./ErrorState";
import { winPct } from "../data/utils";
import { cn } from "../lib/utils";

// Shared table powering the set leaderboard and the per-archetype board, on
// both desktop and mobile. Owns the expanded-row state internally; expanded
// content is rendered by the caller.

export interface LeaderboardTableRow {
  setCode: string;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  rank: number;
  score?: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

export type SortKey = "score" | "trophies" | "events" | "record" | "winPct";
export type SortDir = "asc" | "desc";
export interface SortState {
  key: SortKey;
  dir: SortDir;
}

export const DEFAULT_SORT: SortState = { key: "score", dir: "desc" };
export const DEFAULT_SORT_NOSCORE: SortState = { key: "trophies", dir: "desc" };

const SORT_VALUE: Record<SortKey, (r: LeaderboardTableRow) => number> = {
  score: (r) => r.score ?? 0,
  trophies: (r) => r.trophies,
  events: (r) => r.events,
  record: (r) => r.wins,
  winPct: (r) => r.wins / Math.max(1, r.wins + r.losses),
};

export function sortRows<T extends LeaderboardTableRow>(
  rows: T[],
  { key, dir }: SortState,
): T[] {
  const get = SORT_VALUE[key];
  const sign = dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const av = get(a);
    const bv = get(b);
    if (av !== bv) return sign * (av < bv ? -1 : 1);
    const as = a.score ?? 0;
    const bs = b.score ?? 0;
    if (as !== bs) return bs - as;
    return a.rank - b.rank;
  });
}

const COLS_DESKTOP_WITH_SCORE = "44px 1fr 70px 100px 110px 90px 90px";
const COLS_DESKTOP_NO_SCORE = "44px 1fr 70px 100px 110px 90px";
const COLS_MOBILE_WITH_SCORE = "20px 1fr 44px 50px";
const COLS_MOBILE_NO_SCORE = "20px 1fr 40px 44px 56px";

export function LeaderboardTable<T extends LeaderboardTableRow>({
  rows,
  variant,
  loading = false,
  error,
  emptyMessage,
  renderExpanded,
  /** When false, the caller renders LeaderboardColumnHeader separately (e.g. inside a
   *  page-level sticky chrome). Defaults to true so the table is self-contained. */
  showHeader = true,
  showScore = true,
  sort,
  onSort,
  playerHref,
}: {
  rows: T[] | undefined;
  variant: "desktop" | "mobile";
  loading?: boolean;
  error?: Error | null;
  emptyMessage?: React.ReactNode;
  renderExpanded?: (row: T) => React.ReactNode;
  showHeader?: boolean;
  showScore?: boolean;
  sort?: SortState;
  onSort?: (key: SortKey) => void;
  playerHref?: (row: T) => string | null;
}) {
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const [renderedSlug, setRenderedSlug] = useState<string | null>(null);
  useEffect(() => {
    if (openSlug) {
      setRenderedSlug(openSlug);
      return;
    }
    if (renderedSlug == null) return;
    const t = setTimeout(() => setRenderedSlug(null), 220);
    return () => clearTimeout(t);
  }, [openSlug, renderedSlug]);
  const isMobile = variant === "mobile";

  if (error) return <ErrorState error={error} compact={isMobile} />;
  if (loading) return <LoadingRows variant={variant} />;
  if (!rows || rows.length === 0) return <EmptyState>{emptyMessage}</EmptyState>;

  return (
    <div>
      {showHeader && (
        <LeaderboardColumnHeader variant={variant} showScore={showScore} sort={sort} onSort={onSort} />
      )}
      <div className={cn("flex flex-col", isMobile ? "gap-0" : "gap-[1px]")}>
        {rows.map((r) => {
          const open = openSlug === r.slug;
          const clickable = !!renderExpanded;
          const href = playerHref?.(r) ?? null;
          return (
            <div
              key={r.slug}
              className={cn(
                "transition-colors",
                isMobile && "border-b border-border",
                open ? "bg-surface2" : isMobile ? "bg-transparent" : "bg-surface",
                (clickable || href) && !isMobile && "hover:bg-surface2",
              )}
            >
              {isMobile ? (
                <MobileRow
                  row={r}
                  showScore={showScore}
                  href={href}
                  onToggle={clickable ? () => setOpenSlug(open ? null : r.slug) : undefined}
                />
              ) : (
                <DesktopRow
                  row={r}
                  showScore={showScore}
                  href={href}
                  onToggle={clickable ? () => setOpenSlug(open ? null : r.slug) : undefined}
                />
              )}
              {renderExpanded && (
                <div
                  className={cn(
                    "grid transition-[grid-template-rows] duration-200 ease-out",
                    open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
                  )}
                  aria-hidden={!open}
                >
                  <div className="overflow-hidden">
                    {renderedSlug === r.slug && renderExpanded(r)}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Column header ─────────────────────────────────────────────────────────
// Exported so pages that want to put it inside their own sticky chrome (mobile
// leaderboard) can render it themselves and pass `showHeader={false}` to the table.

export function LeaderboardColumnHeader({
  variant,
  showScore = true,
  sort,
  onSort,
}: {
  variant: "desktop" | "mobile";
  showScore?: boolean;
  sort?: SortState;
  onSort?: (key: SortKey) => void;
}) {
  if (variant === "mobile") {
    const cols = showScore ? COLS_MOBILE_WITH_SCORE : COLS_MOBILE_NO_SCORE;
    return (
      <div
        className="grid gap-3 py-1.5 pl-2 pr-3.5 font-display text-[10px] tracking-[0.2em] text-muted border-b border-border"
        style={{ gridTemplateColumns: cols }}
      >
        <span className="text-center">#</span>
        <span>PLAYER</span>
        <SortHeader label="TR" sortKey="trophies" sort={sort} onSort={onSort} />
        {showScore ? (
          <SortHeader label="PTS" sortKey="score" sort={sort} onSort={onSort} />
        ) : (
          <>
            <SortHeader label="PODS" sortKey="events" sort={sort} onSort={onSort} />
            <SortHeader label="RECORD" sortKey="record" sort={sort} onSort={onSort} />
          </>
        )}
      </div>
    );
  }
  const cols = showScore ? COLS_DESKTOP_WITH_SCORE : COLS_DESKTOP_NO_SCORE;
  return (
    <div
      className="grid gap-x-3 py-2.5 pl-2 pr-5 mb-1 font-display text-[11px] tracking-[0.2em] text-muted"
      style={{ gridTemplateColumns: cols }}
    >
      <span className="text-center">RANK</span>
      <span>PLAYER</span>
      <SortHeader label="TROPHIES" sortKey="trophies" sort={sort} onSort={onSort} />
      <SortHeader label="EVENTS" sortKey="events" sort={sort} onSort={onSort} />
      <SortHeader label="RECORD" sortKey="record" sort={sort} onSort={onSort} />
      <SortHeader label="WIN %" sortKey="winPct" sort={sort} onSort={onSort} />
      {showScore && <SortHeader label="POINTS" sortKey="score" sort={sort} onSort={onSort} />}
    </div>
  );
}

function SortHeader({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  sort?: SortState;
  onSort?: (key: SortKey) => void;
}) {
  if (!onSort) {
    return <span className="text-right">{label}</span>;
  }
  const active = sort?.key === sortKey;
  const Icon = active && sort?.dir === "asc" ? ChevronUp : ChevronDown;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      aria-label={`Sort by ${label}`}
      aria-sort={active ? (sort?.dir === "asc" ? "ascending" : "descending") : "none"}
      className={cn(
        "relative block w-full text-right cursor-pointer transition-colors tracking-[inherit] text-[inherit] font-[inherit]",
        active ? "text-text" : "hover:text-text",
      )}
    >
      <span>{label}</span>
      <Icon
        size={11}
        strokeWidth={2.5}
        className={cn(
          "absolute left-full top-1/2 -translate-y-1/2 ml-0.5 shrink-0",
          active ? "opacity-100" : "opacity-30",
        )}
        aria-hidden="true"
      />
    </button>
  );
}

// ─── Row variants ──────────────────────────────────────────────────────────

function DesktopRow({
  row,
  showScore,
  onToggle,
  href,
}: {
  row: LeaderboardTableRow;
  showScore: boolean;
  onToggle?: () => void;
  href?: string | null;
}) {
  const cols = showScore ? COLS_DESKTOP_WITH_SCORE : COLS_DESKTOP_NO_SCORE;
  const rowLinked = !!href && !onToggle;
  const body = (
    <>
      <span className="mono text-[13px] text-muted text-center">{row.rank}</span>
      <PlayerCell row={row} avatarSize={30} nameSize={18} linked={rowLinked} />
      <TrophyCell trophies={row.trophies} compact={false} large={!showScore} />
      <span className="mono text-right text-[13px] text-muted">{row.events}</span>
      <Record className="mono text-right text-[13px]" wins={row.wins} losses={row.losses} />
      <span className="mono text-right text-[13px] text-muted">{winPct(row.wins, row.losses)}%</span>
      {showScore && <ScoreCell score={row.score ?? 0} large />}
    </>
  );
  if (rowLinked) {
    return (
      <Link
        to={href!}
        className="group/row grid items-center gap-x-3 py-2.5 pl-2 pr-5 cursor-pointer no-underline text-inherit"
        style={{ gridTemplateColumns: cols }}
      >
        {body}
      </Link>
    );
  }
  return (
    <div
      onClick={onToggle}
      className={cn(
        "grid items-center gap-x-3 py-2.5 pl-2 pr-5",
        onToggle && "cursor-pointer",
      )}
      style={{ gridTemplateColumns: cols }}
    >
      {body}
    </div>
  );
}

function MobileRow({
  row,
  showScore,
  onToggle,
  href,
}: {
  row: LeaderboardTableRow;
  showScore: boolean;
  onToggle?: () => void;
  href?: string | null;
}) {
  const cols = showScore ? COLS_MOBILE_WITH_SCORE : COLS_MOBILE_NO_SCORE;
  const rowLinked = !!href && !onToggle;
  const body = (
    <>
      <span className="mono text-[12px] text-muted text-center">{row.rank}</span>
      <PlayerCell row={row} avatarSize={26} nameSize={17} linked={rowLinked} />
      <TrophyCell trophies={row.trophies} compact large={!showScore} />
      {showScore ? (
        <span className="font-display text-right text-[18px] tracking-[0.02em] tabular-nums leading-none">
          {fmtPts(row.score ?? 0)}
        </span>
      ) : (
        <>
          <span className="mono text-right text-[13px] text-muted tabular-nums">{row.events}</span>
          <Record className="mono text-right text-[13px]" wins={row.wins} losses={row.losses} />
        </>
      )}
    </>
  );
  if (rowLinked) {
    return (
      <Link
        to={href!}
        className="group/row py-[9px] pl-2 pr-3.5 grid gap-3 items-center cursor-pointer no-underline text-inherit"
        style={{ gridTemplateColumns: cols }}
      >
        {body}
      </Link>
    );
  }
  return (
    <div
      onClick={onToggle}
      className={cn(
        "py-[9px] pl-2 pr-3.5 grid gap-3 items-center",
        onToggle && "cursor-pointer",
      )}
      style={{ gridTemplateColumns: cols }}
    >
      {body}
    </div>
  );
}

// ─── Subcells ──────────────────────────────────────────────────────────────

function PlayerCell({
  row,
  avatarSize,
  nameSize,
  linked = false,
}: {
  row: LeaderboardTableRow;
  avatarSize: number;
  nameSize: number;
  linked?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <AAvatar displayName={row.displayName} avatarUrl={row.avatarUrl} size={avatarSize} />
      <div
        className={cn(
          "font-display leading-none tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis",
          linked && "transition-colors group-hover/row:text-green",
        )}
        style={{ fontSize: nameSize }}
      >
        {row.displayName.toUpperCase()}
      </div>
    </div>
  );
}

function TrophyCell({
  trophies,
  compact,
  large = false,
}: {
  trophies: number;
  compact: boolean;
  large?: boolean;
}) {
  const iconSize = compact ? 15 : 18;
  const textSize = compact
    ? large
      ? "text-[18px]"
      : "text-[15px]"
    : "text-[18px]";
  return (
    <div
      className={cn(
        "text-right flex items-center justify-end",
        compact ? "gap-1" : "gap-1.5",
      )}
    >
      <Trophy size={iconSize} color="#ffc63a" />
      <span className={cn("font-display tracking-[0.02em] tabular-nums leading-none", textSize)}>
        {trophies}
      </span>
    </div>
  );
}

function ScoreCell({ score, large }: { score: number; large?: boolean }) {
  return (
    <div
      className={cn(
        "text-right font-display tracking-[0.02em] tabular-nums",
        large ? "text-[24px] leading-none" : "text-[18px] leading-none",
      )}
    >
      {fmtPts(score)}
    </div>
  );
}

// ─── States ────────────────────────────────────────────────────────────────

function LoadingRows({ variant }: { variant: "desktop" | "mobile" }) {
  return (
    <div className={variant === "mobile" ? "py-2 px-3.5" : "py-3 px-3.5"}>
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="grid gap-2.5 py-2.5 border-b border-border items-center"
          style={{ gridTemplateColumns: "32px 1fr 60px" }}
        >
          <div className="h-8 bg-surface2" />
          <div
            className="h-3.5 bg-surface2 animate-pulse"
            style={{ width: `${50 + i * 8}%` }}
          />
          <div className="h-3.5 bg-surface2" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ children }: { children?: React.ReactNode }) {
  return (
    <div className="p-10 text-center">
      <div className="font-display text-[22px] tracking-[0.04em] text-text">NO EVENTS YET</div>
      <div className="mono text-[11px] text-muted mt-2">
        {children ?? "NO PLAYER DATA FOR THIS SET / FILTER YET. CHECK BACK SOON."}
      </div>
    </div>
  );
}
