// Mock API layer.
//
// Mirrors the future Supabase-backed shape: each function returns a Promise of
// rows in the camelCase types from `src/types/leaderboard.ts`. Swap-in checklist
// when wiring real Supabase:
//   1. Replace each function body with a `supabase.from('public_*').select(...)`
//      call against the curated public view.
//   2. Run the rows through `adapter.ts` to convert snake_case -> camelCase.
//   3. Keep the function signatures unchanged — the hook layer in `hooks.ts`
//      and every component above it stays put.
//
// We hand-roll the latency so loading states render naturally during dev.

import type {
  ArchetypeLeaderboardRow,
  LeaderboardRow,
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerProfile,
  RecentTrophy,
  SetSummary,
} from "../types/leaderboard";

import { setsFixture } from "./fixtures/sets";
import { leaderboardSosFixture } from "./fixtures/leaderboard-sos";
import { archetypeSosWrFixture } from "./fixtures/archetype-sos-wr";
import {
  chonceDraftEvents,
  chonceFormatBreakdown,
} from "./fixtures/player-chonce";
import {
  nlaframboiseDraftEvents,
  nlaframboiseFormatBreakdown,
} from "./fixtures/player-nlaframboise";
import {
  elfandorDraftEvents,
  elfandorFormatBreakdown,
} from "./fixtures/player-elfandor";
import {
  flutterdevDraftEvents,
  flutterdevFormatBreakdown,
} from "./fixtures/player-flutterdev";
import {
  oophiesDraftEvents,
  oophiesFormatBreakdown,
} from "./fixtures/player-oophies";

// Real per-player data keyed by slug. Other slugs fall through to the synth
// generator below.
const REAL_BREAKDOWNS: Record<string, PlayerFormatBreakdown[]> = {
  chonce: chonceFormatBreakdown,
  nlaframboise: nlaframboiseFormatBreakdown,
  elfandor: elfandorFormatBreakdown,
  flutterdev: flutterdevFormatBreakdown,
  oophies: oophiesFormatBreakdown,
};

const REAL_DRAFT_EVENTS: Record<string, PlayerDraftEvent[]> = {
  chonce: chonceDraftEvents,
  nlaframboise: nlaframboiseDraftEvents,
  elfandor: elfandorDraftEvents,
  flutterdev: flutterdevDraftEvents,
  oophies: oophiesDraftEvents,
};

const FAKE_LATENCY_MS = 80;

const wait = <T,>(value: T): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(value), FAKE_LATENCY_MS));

// ─── public_sets ─────────────────────────────────────────────────────────────
export const fetchSets = (): Promise<SetSummary[]> => wait(setsFixture);

// ─── public_leaderboard ──────────────────────────────────────────────────────
// Format filter is applied client-side over the cached rows in the hook layer
// (per spec §7), so this fetcher returns the full set unfiltered.
export const fetchLeaderboard = (setCode: string): Promise<LeaderboardRow[]> => {
  if (setCode === "SOS") return wait(leaderboardSosFixture);
  // Other sets are scheduled placeholders with no player data yet.
  return wait([]);
};

// ─── per-format leaderboard (fixture-side, mirrors realApi join) ─────────────
// Fixtures only have full per-format breakdowns for the 5 players we curated.
// For everyone else we approximate using synthBreakdown so the table still
// has 30+ rows to render in dev. Real prod uses the actual breakdown view.
export const fetchFormatLeaderboard = (
  setCode: string,
  format: string,
): Promise<LeaderboardRow[]> => {
  if (setCode !== "SOS") return wait([]);

  const rows = leaderboardSosFixture
    .map((player) => {
      const breakdown = REAL_BREAKDOWNS[player.slug] ?? synthBreakdown(player);
      const fmt = breakdown.find((f) => f.formatLabel === format);
      if (!fmt || fmt.events === 0) return null;
      return {
        setCode,
        slug: player.slug,
        displayName: player.displayName,
        avatarUrl: player.avatarUrl,
        rank: 0,
        score: fmt.scoreContribution,
        trophies: fmt.trophies,
        events: fmt.events,
        wins: fmt.wins,
        losses: fmt.losses,
        lastCalculatedAt: player.lastCalculatedAt,
      } satisfies LeaderboardRow;
    })
    .filter((r): r is LeaderboardRow => r !== null)
    .sort((a, b) => b.score - a.score)
    .map((r, i) => ({ ...r, rank: i + 1 }));

  return wait(rows);
};

// ─── public_archetype_leaderboard ────────────────────────────────────────────
// Switching archetype switches the data source (different scoring), per spec §7.
export const fetchArchetypeLeaderboard = (
  setCode: string,
  archetype: string
): Promise<ArchetypeLeaderboardRow[]> => {
  if (setCode === "SOS" && archetype === "WR") return wait(archetypeSosWrFixture);
  // Any other (set, archetype) cell — synthesise a slice from the WR fixture so
  // the UI has data to render. Real backend returns the proper subset-replay rows.
  const slice = archetypeSosWrFixture
    .slice(0, 14)
    .map((row, i) => ({
      ...row,
      archetype,
      rank: i + 1,
      score: Math.max(0, row.score * (0.4 + Math.random() * 0.4)),
      trophies: Math.max(0, Math.round(row.trophies * 0.6)),
    }));
  return wait(slice);
};

// ─── public_player_format_breakdown + public_leaderboard ─────────────────────
export const fetchPlayerProfile = (
  slug: string,
  setCode: string
): Promise<PlayerProfile | null> => {
  const headline = leaderboardSosFixture.find((r) => r.slug === slug);
  if (!headline) return wait(null);
  const breakdown = REAL_BREAKDOWNS[slug] ?? synthBreakdown(headline);
  return wait({
    slug: headline.slug,
    displayName: headline.displayName,
    avatarUrl: headline.avatarUrl,
    setCode,
    rank: headline.rank,
    score: headline.score,
    trophies: headline.trophies,
    events: headline.events,
    wins: headline.wins,
    losses: headline.losses,
    formatBreakdown: breakdown,
  });
};

// ─── public_player_draft_events ──────────────────────────────────────────────
// Loaded lazily per player; not fetched up-front for the leaderboard.
export const fetchPlayerDraftEvents = (
  slug: string,
  _setCode: string
): Promise<PlayerDraftEvent[]> => {
  const real = REAL_DRAFT_EVENTS[slug];
  if (real) return wait(real);
  return wait(synthDraftEvents(slug));
};

// ─── public_recent_trophies ──────────────────────────────────────────────────
// Aggregates trophy events across all players we have draft event data for,
// joined with their display names from the leaderboard. Sorted by finished_at
// DESC so the most recent runs come first.
//
// In production this becomes a view: SELECT trophy events JOIN players. For
// fixtures, we walk REAL_DRAFT_EVENTS — only 5 players have real event logs,
// but those 5 cover the top of the leaderboard so the recent-trophy feed is
// representative.
export const fetchRecentTrophies = (
  setCode: string,
  limit = 8,
): Promise<RecentTrophy[]> => {
  if (setCode !== "SOS") return wait([]);
  const out: RecentTrophy[] = [];
  for (const events of Object.values(REAL_DRAFT_EVENTS)) {
    for (const e of events) {
      if (!e.isTrophy) continue;
      const headline = leaderboardSosFixture.find((r) => r.slug === e.slug);
      if (!headline) continue;
      out.push({
        setCode,
        slug: e.slug,
        displayName: headline.displayName,
        avatarUrl: headline.avatarUrl,
        format: e.format,
        colors: e.colors,
        wins: e.wins,
        losses: e.losses,
        finishedAt: e.finishedAt,
      });
    }
  }
  out.sort((a, b) => (a.finishedAt < b.finishedAt ? 1 : -1));
  return wait(out.slice(0, limit));
};

// ─────────────────────────────────────────────────────────────────────────────
// Synth helpers — produce plausible per-player breakdowns and event logs for any
// slug not in the curated fixtures, so all 48 leaderboard rows are click-through.
// Real backend returns the actual rows; these only exist in mock mode.

function synthBreakdown(row: LeaderboardRow): PlayerFormatBreakdown[] {
  const labels = ["Premier", "Trad", "Quick", "Sealed", "Trad Sealed"];
  const weights = [0.45, 0.4, 0.1, 0.04, 0.01];
  return labels.map((formatLabel, i) => {
    const w = weights[i];
    return {
      setCode: row.setCode,
      slug: row.slug,
      formatLabel,
      events: Math.round(row.events * w),
      wins: Math.round(row.wins * w),
      losses: Math.round(row.losses * w),
      trophies: Math.round(row.trophies * w),
      scoreContribution: Math.round(row.score * w * 100) / 100,
    };
  });
}

function synthDraftEvents(slug: string): PlayerDraftEvent[] {
  const archetypes = ["WR", "UR", "BG", "WB", "UB", "RG", "WG", "UG", "BR"];
  const formats = ["PremierDraft", "TradDraft", "QuickDraft"];
  const out: PlayerDraftEvent[] = [];
  let day = new Date("2026-05-08T00:00:00Z").getTime();
  for (let i = 0; i < 24; i++) {
    const wins = Math.floor(Math.random() * 8);
    const losses = wins >= 7 ? Math.floor(Math.random() * 3) : 3;
    out.push({
      slug,
      setCode: "SOS",
      eventId: `synth-${slug}-${i}`,
      format: formats[i % formats.length],
      expansion: "SOS",
      wins,
      losses,
      isTrophy: wins >= 7,
      colors: archetypes[i % archetypes.length],
      startedAt: new Date(day - 1000 * 60 * 90).toISOString(),
      finishedAt: new Date(day).toISOString(),
    });
    day -= 1000 * 60 * 60 * (4 + Math.random() * 8);
  }
  return out;
}
