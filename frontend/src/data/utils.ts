// Pure helpers shared by pages and components.
// Anything stateless that previously got inlined or duplicated lives here.

import type { LeaderboardRow, SetSummary } from "../types/leaderboard";

const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"] as const;

const MONTHS_SHORT = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."] as const;

// "May 8" / "Apr. 8" / "Dec. 23" — parses the YYYY-MM-DD prefix directly to
// avoid timezone shifts on UTC-stored draft timestamps
export function fmtShortDate(iso: string): string {
  const month = parseInt(iso.slice(5, 7), 10);
  const day = parseInt(iso.slice(8, 10), 10);
  if (!month || !day) return "";
  return `${MONTHS_SHORT[month - 1]} ${day}`;
}

// Win percentage as a fixed-precision string, safe against zero-game players.
export function winPct(wins: number, losses: number, digits = 1): string {
  return ((wins / Math.max(1, wins + losses)) * 100).toFixed(digits);
}

// Strip splash colors (lowercase) from a 17lands color string, leaving uppercase main colors.
export function mainColors(colors: string | null | undefined): string {
  if (!colors) return "";
  return colors.replace(/[a-z]/g, "");
}

// Sort main colors into WUBRG order. Used for archetype normalization.
export function wubrgSort(colors: string): string {
  const order = "WUBRG";
  return [...colors].sort((a, b) => order.indexOf(a) - order.indexOf(b)).join("");
}

// WUBRG-sorted main colors only — splashes dropped
export function colorsOf(colors: string | null | undefined): string {
  return wubrgSort(mainColors(colors));
}

// Distinct colors played (main + splash deduped)
export function effectiveColorCount(colors: string | null | undefined): number {
  if (!colors) return 0;
  const seen = new Set<string>();
  for (const c of colors) {
    const u = c.toUpperCase();
    if ("WUBRG".includes(u)) seen.add(u);
  }
  return seen.size;
}

function parseLocalDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function fmtRange(start: string, end: string | null | undefined, today: Date = new Date()): string {
  if (!end) return "";
  const s = parseLocalDate(start);
  const e = parseLocalDate(end);
  const base = `${MONTHS[s.getMonth()]} ${s.getDate()} — ${MONTHS[e.getMonth()]} ${e.getDate()}`;
  return e.getFullYear() !== today.getFullYear() ? `${base}, ${e.getFullYear()}` : base;
}

export function weekOfSet(set: SetSummary | undefined, today: Date = new Date()): string | null {
  if (!set?.startDate || !set.endDate) return null;
  const start = parseLocalDate(set.startDate).getTime();
  const end = parseLocalDate(set.endDate).getTime();
  const now = today.getTime();
  if (now > end) return null;
  const totalWeeks = Math.max(1, Math.ceil((end - start) / (7 * 24 * 60 * 60 * 1000)));
  const elapsedWeeks = Math.max(1, Math.min(totalWeeks, Math.ceil((now - start) / (7 * 24 * 60 * 60 * 1000))));
  return `WEEK ${elapsedWeeks} OF ${totalWeeks}`;
}

// Most-recent `lastCalculatedAt` across rows, rendered as a relative-time
// string ("5M AGO", "2H AGO", "NOW") for the "UPDATED" badge.
export function lastUpdated(rows: ReadonlyArray<{ lastCalculatedAt: string }> | undefined): string {
  if (!rows || rows.length === 0) return "—";
  const latest = rows.reduce(
    (m, r) => (r.lastCalculatedAt > m ? r.lastCalculatedAt : m),
    rows[0].lastCalculatedAt
  );
  const rel = relativeTime(latest);
  return rel === "now" ? "NOW" : `${rel.toUpperCase()} AGO`;
}

// Total events across rows, locale-formatted with commas.
export function sumEvents(rows: ReadonlyArray<{ events: number }> | undefined): string {
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

// Maps any raw 17lands format string OR a backend `format_label` group
// (Premier / Trad / Quick / Sealed / LCQ Draft 1 / LCQ Draft 2) to a
// presentation-ready name. Unknowns fall through unchanged.
const FORMAT_DISPLAY: Record<string, string> = {
  Premier: "Premier Draft",
  Trad: "Traditional Draft",
  Quick: "Quick Draft",
  Sealed: "Sealed",
  "LCQ Draft 1": "LCQ Draft 1",
  "LCQ Draft 2": "LCQ Draft 2",
  PremierDraft: "Premier Draft",
  TradDraft: "Traditional Draft",
  QuickDraft: "Quick Draft",
  TradSealed: "Traditional Sealed",
  ArenaDirect_Sealed: "Arena Direct",
  QualifierPlayInSealed: "Qualifier Play-In",
  PickTwoDraft: "Pick Two Draft",
  Emblem_QuickDraft: "Quick Draft",
  LimitedChampionshipQualifier_Draft1: "LCQ Draft 1",
  LimitedChampionshipQualifier_Draft2: "LCQ Draft 2",
};

export function prettyFormat(format: string): string {
  return FORMAT_DISPLAY[format] ?? format;
}

