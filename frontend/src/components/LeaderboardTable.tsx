import React, { useState } from "react";
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
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

const COLS_DESKTOP = "60px 1fr 110px 100px 110px 90px 130px";
const COLS_MOBILE = "18px 1fr 44px 50px";

export function LeaderboardTable<T extends LeaderboardTableRow>({
  rows,
  variant,
  loading = false,
  error,
  emptyMessage,
  renderExpanded,
}: {
  rows: T[] | undefined;
  variant: "desktop" | "mobile";
  loading?: boolean;
  error?: Error | null;
  emptyMessage?: React.ReactNode;
  renderExpanded?: (row: T) => React.ReactNode;
}) {
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const isMobile = variant === "mobile";

  if (error) return <ErrorState error={error} compact={isMobile} />;
  if (loading) return <LoadingRows variant={variant} />;
  if (!rows || rows.length === 0) return <EmptyState>{emptyMessage}</EmptyState>;

  return (
    <div>
      <ColumnHeader variant={variant} />
      <div className={cn("flex flex-col", isMobile ? "gap-0" : "gap-0.5")}>
        {rows.map((r) => {
          const open = openSlug === r.slug;
          return (
            <div
              key={r.slug}
              className={cn(
                "transition-colors",
                isMobile && "border-b border-border",
                open ? "bg-surface2" : isMobile ? "bg-transparent" : "bg-surface",
                !isMobile && "hover:bg-surface2",
              )}
            >
              {isMobile ? (
                <MobileRow row={r} onToggle={() => setOpenSlug(open ? null : r.slug)} />
              ) : (
                <DesktopRow row={r} onToggle={() => setOpenSlug(open ? null : r.slug)} />
              )}
              {open && renderExpanded && renderExpanded(r)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Column header ─────────────────────────────────────────────────────────

function ColumnHeader({ variant }: { variant: "desktop" | "mobile" }) {
  if (variant === "mobile") {
    return (
      <div
        className="grid gap-2 py-1.5 pl-2.5 pr-3.5 font-display text-[10px] tracking-[0.2em] text-muted border-b border-border"
        style={{ gridTemplateColumns: COLS_MOBILE }}
      >
        <span className="text-right">#</span>
        <span>PLAYER</span>
        <span className="text-right">TR</span>
        <span className="text-right">PTS</span>
      </div>
    );
  }
  return (
    <div
      className="grid py-2.5 px-5 mb-1 font-display text-[11px] tracking-[0.2em] text-muted"
      style={{ gridTemplateColumns: COLS_DESKTOP }}
    >
      <span>RANK</span>
      <span>PLAYER</span>
      <span className="text-right">TROPHIES</span>
      <span className="text-right">EVENTS</span>
      <span className="text-right">RECORD</span>
      <span className="text-right">WIN %</span>
      <span className="text-right">POINTS</span>
    </div>
  );
}

// ─── Row variants ──────────────────────────────────────────────────────────

function DesktopRow({ row, onToggle }: { row: LeaderboardTableRow; onToggle: () => void }) {
  return (
    <div
      onClick={onToggle}
      className="grid items-center py-2.5 px-5 cursor-pointer"
      style={{ gridTemplateColumns: COLS_DESKTOP }}
    >
      <span className="mono text-[13px] text-muted">{row.rank}</span>
      <PlayerCell row={row} avatarSize={30} nameSize={16} />
      <TrophyCell trophies={row.trophies} compact={false} />
      <span className="mono text-right text-[13px] text-muted">{row.events}</span>
      <Record className="mono text-right text-[13px]" wins={row.wins} losses={row.losses} />
      <span className="mono text-right text-[13px] text-muted">{winPct(row.wins, row.losses)}%</span>
      <ScoreCell score={row.score} large />
    </div>
  );
}

function MobileRow({ row, onToggle }: { row: LeaderboardTableRow; onToggle: () => void }) {
  return (
    <div
      onClick={onToggle}
      className="py-[9px] pl-2.5 pr-3.5 grid gap-2 items-center cursor-pointer"
      style={{ gridTemplateColumns: COLS_MOBILE }}
    >
      <span className="mono text-[12px] text-muted text-right">{row.rank}</span>
      <PlayerCell row={row} avatarSize={26} nameSize={15} />
      <TrophyCell trophies={row.trophies} compact />
      <span className="mono text-right text-[15px] font-bold">{fmtPts(row.score)}</span>
    </div>
  );
}

// ─── Subcells ──────────────────────────────────────────────────────────────

function PlayerCell({
  row,
  avatarSize,
  nameSize,
}: {
  row: LeaderboardTableRow;
  avatarSize: number;
  nameSize: number;
}) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <AAvatar displayName={row.displayName} avatarUrl={row.avatarUrl} size={avatarSize} />
      <div
        className="font-display tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis"
        style={{ fontSize: nameSize }}
      >
        {row.displayName.toUpperCase()}
      </div>
    </div>
  );
}

function TrophyCell({ trophies, compact }: { trophies: number; compact: boolean }) {
  return (
    <div
      className={cn(
        "text-right flex items-center justify-end",
        compact ? "gap-[3px]" : "gap-1.5",
      )}
    >
      <Trophy size={compact ? 10 : 14} color="#ffc63a" />
      <span className={cn("mono font-semibold", compact ? "text-[12px]" : "text-[15px]")}>
        {trophies}
      </span>
    </div>
  );
}

function ScoreCell({ score, large }: { score: number; large?: boolean }) {
  return (
    <div
      className={cn(
        "mono text-right font-bold font-display tracking-[0.02em]",
        large ? "text-[22px]" : "text-[15px]",
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
      <div className="font-display text-[22px] tracking-[0.04em] text-text">NO RUNS YET</div>
      <div className="mono text-[11px] text-muted mt-2">
        {children ?? "NO PLAYER DATA FOR THIS SET / FILTER YET. CHECK BACK SOON."}
      </div>
    </div>
  );
}
