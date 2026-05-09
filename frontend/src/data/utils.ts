// Pure helpers shared by pages and components.
// Anything stateless that previously got inlined or duplicated lives here.

import type { LeaderboardRow, SetSummary } from "../types/leaderboard";

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"] as const;

// Win percentage as a fixed-precision string, safe against zero-game players.
export function winPct(wins: number, losses: number, digits = 1): string {
  return ((wins / Math.max(1, wins + losses)) * 100).toFixed(digits);
}

// Strip splash colors (lowercase) from a 17lands color string, leaving uppercase main colors.
export function mainColors(colors: string): string {
  return colors.replace(/[a-z]/g, "");
}

// Sort main colors into WUBRG order. Used for archetype normalization.
export function wubrgSort(colors: string): string {
  const order = "WUBRG";
  return [...colors].sort((a, b) => order.indexOf(a) - order.indexOf(b)).join("");
}

// Derive the WUBRG-sorted main-color archetype from a raw 17lands color string.
export function archetypeOf(colors: string): string {
  return wubrgSort(mainColors(colors));
}

// Pretty date range used in set hero (e.g. "APR 21 — JUN 22").
export function fmtRange(start: string, end: string | null | undefined): string {
  if (!end) return "";
  const s = new Date(start);
  const e = new Date(end);
  return `${MONTHS[s.getMonth()]} ${s.getDate()} — ${MONTHS[e.getMonth()]} ${e.getDate()}`;
}

// "WEEK N OF M" for a set, derived from the date range. Returns null when the set
// is closed-ended but today is outside the window (returns "WEEK M OF M" instead).
export function weekOfSet(set: SetSummary | undefined, today: Date = new Date()): string | null {
  if (!set?.startDate || !set.endDate) return null;
  const start = new Date(set.startDate).getTime();
  const end = new Date(set.endDate).getTime();
  const now = today.getTime();
  const totalWeeks = Math.max(1, Math.ceil((end - start) / (7 * 24 * 60 * 60 * 1000)));
  const elapsedWeeks = Math.max(1, Math.min(totalWeeks, Math.ceil((now - start) / (7 * 24 * 60 * 60 * 1000))));
  return `WEEK ${elapsedWeeks} OF ${totalWeeks}`;
}

// Most-recent `lastCalculatedAt` across rows, formatted as HH:MM UTC for the
// "UPDATED" badge.
export function lastUpdated(rows: LeaderboardRow[] | undefined): string {
  if (!rows || rows.length === 0) return "—";
  const latest = rows.reduce(
    (m, r) => (r.lastCalculatedAt > m ? r.lastCalculatedAt : m),
    rows[0].lastCalculatedAt
  );
  return latest.slice(11, 16) + " UTC";
}

// Total events across rows, locale-formatted with commas.
export function sumEvents(rows: LeaderboardRow[] | undefined): string {
  if (!rows) return "0";
  return rows.reduce((s, r) => s + r.events, 0).toLocaleString();
}

// Compact relative time ("2h", "3d", "1w") suitable for sidebar timestamps.
// Only goes one unit deep; "now" for events under a minute old.
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  const diffMs = now.getTime() - then;
  if (diffMs < 60_000) return "now";
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w`;
}

// Short visual label for a 17lands format string (e.g. "PremierDraft" → "PREM").
export function shortFormatLabel(format: string): string {
  const stripped = format.replace("Draft", "");
  return stripped.slice(0, 4).toUpperCase();
}
