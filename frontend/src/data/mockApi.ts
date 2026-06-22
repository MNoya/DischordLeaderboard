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
  ColorsLeaderboardRow,
  ColorsSummary,
  CubeSeason,
  LeaderboardRow,
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerIdentity,
  PlayerProfile,
  PodDraftArtifact,
  PodEventMatchRow,
  PodEventParticipantRow,
  PodEventReplayRow,
  PodEventSummary,
  PodLeaderboardRow,
  PodSetCode,
  RecentTrophy,
  SetSummary,
} from "../types/leaderboard";
import type { Card, P0P1Pick, P0P1PickStat, SlotKey } from "../types/p0p1";
import type { Episode } from "./episodes";
import {
  podDraftArtifactFixture,
  podEventsFixture,
  podEventMatchesFixture,
  podEventParticipantsFixture,
  podEventReplaysFixture,
  podLeaderboardFixtureRaw,
  podSetCodesFixture,
} from "./fixtures/pod-events";

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

export const fetchCubeSeasons = (): Promise<CubeSeason[]> => wait([]);

export const fetchDbEpisodes = (): Promise<Episode[]> => wait([]);

export const fetchAvailableFormats = (_setCode: string): Promise<string[]> =>
  wait(["Premier", "Trad", "Sealed", "Quick", "LCQ Draft 1", "LCQ Draft 2"]);

export const fetchFormatColorsLeaderboard = (
  _setCode: string,
  _format: string,
  _archetypes: string | string[],
) => wait([] as never[]);

// ─── public_leaderboard ──────────────────────────────────────────────────────
// Format filter is applied client-side over the cached rows in the hook layer
// (per spec §7), so this fetcher returns the full set unfiltered.
export const fetchLeaderboard = (setCode: string): Promise<LeaderboardRow[]> => {
  if (setCode === "SOS") return wait(leaderboardSosFixture);
  // Other sets are scheduled placeholders with no player data yet.
  return wait([]);
};

// ─── colors summary (fixture-side) ──────────────────────────────────────────
// Aggregates color combos from the curated player draft events. Only the 5
// fixture players contribute, but they cover the SOS top of the leaderboard so
// the list is representative enough for dev.
import { colorsOf } from "./utils";
import { matchesFormatFilter } from "./filters";

export const fetchColorsSummary = (setCode: string): Promise<ColorsSummary[]> => {
  if (setCode !== "SOS") return wait([]);

  const agg = new Map<string, { trophies: number; events: number; players: Set<string> }>();
  for (const events of Object.values(REAL_DRAFT_EVENTS)) {
    for (const e of events) {
      const c = colorsOf(e.colors);
      if (!c) continue;
      const cur = agg.get(c) ?? { trophies: 0, events: 0, players: new Set() };
      cur.events += 1;
      if (e.isTrophy) cur.trophies += 1;
      cur.players.add(e.slug);
      agg.set(c, cur);
    }
  }

  return wait(
    Array.from(agg.entries())
      .map(([colors, v]) => ({
        setCode,
        colors,
        trophies: v.trophies,
        events: v.events,
        players: v.players.size,
      }))
      .sort((a, b) => b.trophies - a.trophies),
  );
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
// Switching color combo switches the data source (different scoring), per spec §7.
export const fetchColorsLeaderboard = (
  setCode: string,
  colors: string
): Promise<ColorsLeaderboardRow[]> => {
  if (setCode === "SOS" && colors === "WR") return wait(archetypeSosWrFixture);
  // Any other (set, colors) cell — synthesise a slice from the WR fixture so
  // the UI has data to render. Real backend returns the proper subset-replay rows.
  const slice = archetypeSosWrFixture
    .slice(0, 14)
    .map((row, i) => ({
      ...row,
      colors,
      rank: i + 1,
      score: Math.max(0, row.score * (0.4 + Math.random() * 0.4)),
      trophies: Math.max(0, Math.round(row.trophies * 0.6)),
    }));
  return wait(slice);
};

// Mock-side OTHER — return a synthetic slice so the UI has rows to render.
export const fetchOtherColorsLeaderboard = (
  setCode: string,
  _otherCombos: string[],
  _formatFilter?: string,
): Promise<ColorsLeaderboardRow[]> => {
  if (setCode !== "SOS") return wait([]);
  const slice = archetypeSosWrFixture.slice(10, 18).map((row, i) => ({
    ...row,
    colors: "OTHER",
    rank: i + 1,
    score: Math.max(0, row.score * 0.5),
    trophies: Math.max(0, Math.round(row.trophies * 0.4)),
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

export const fetchPlayerSlugByDiscordId = (_discordId: string): Promise<string | null> =>
  wait(leaderboardSosFixture[0]?.slug ?? null);

// ─── public_player (identity, set-independent) ───────────────────────────────
export const fetchPlayerIdentity = (slug: string): Promise<PlayerIdentity | null> => {
  const row = leaderboardSosFixture.find((r) => r.slug === slug);
  if (!row) return wait(null);
  return wait({ slug: row.slug, displayName: row.displayName, avatarUrl: row.avatarUrl });
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
  return wait(_allTrophiesFor(setCode).slice(0, limit));
};

export const fetchFormatRecentTrophies = (
  setCode: string,
  format: string,
): Promise<RecentTrophy[]> => {
  return wait(_allTrophiesFor(setCode).filter((t) => matchesFormatFilter(t.format, format)));
};

function _allTrophiesFor(setCode: string): RecentTrophy[] {
  if (setCode !== "SOS") return [];
  const out: RecentTrophy[] = [];
  for (const events of Object.values(REAL_DRAFT_EVENTS)) {
    for (const e of events) {
      if (!e.isTrophy || !e.finishedAt) continue;
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
  return out.sort((a, b) => (a.finishedAt < b.finishedAt ? 1 : -1));
}

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

export const fetchPodEvents = (setCode: string): Promise<PodEventSummary[]> => {
  return wait(podEventsFixture.filter((e) => e.setCode === setCode));
};

export const fetchPodEventParticipants = (
  eventId: string,
): Promise<PodEventParticipantRow[]> => {
  return wait(podEventParticipantsFixture.filter((p) => p.eventId === eventId));
};

export const fetchPodDraftArtifact = (eventId: string): Promise<PodDraftArtifact | null> => {
  return wait(podDraftArtifactFixture[eventId] ?? null);
};

export const fetchPodEventBySlug = (slug: string): Promise<PodEventSummary | null> => {
  return wait(podEventsFixture.find((e) => e.slug === slug) ?? null);
};

export const fetchPodEventMatches = (eventId: string): Promise<PodEventMatchRow[]> => {
  return wait(
    podEventMatchesFixture
      .filter((m) => m.eventId === eventId)
      .slice()
      .sort((a, b) => a.round - b.round),
  );
};

export const fetchPodEventReplays = (eventId: string): Promise<PodEventReplayRow[]> => {
  return wait(
    podEventReplaysFixture
      .filter((r) => r.eventId === eventId)
      .slice()
      .sort((a, b) => (a.gameTime < b.gameTime ? -1 : a.gameTime > b.gameTime ? 1 : 0)),
  );
};

export const fetchPodLeaderboard = (setCode: string): Promise<PodLeaderboardRow[]> => {
  const rows = podLeaderboardFixtureRaw
    .filter((r) => r.setCode === setCode)
    .slice()
    .sort((a, b) => {
      if (b.trophies !== a.trophies) return b.trophies - a.trophies;
      if (b.wins !== a.wins) return b.wins - a.wins;
      return a.events - b.events;
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
  return wait(rows);
};

export const fetchPodSetCodes = (): Promise<PodSetCode[]> => wait(podSetCodesFixture);

// --- P0P1 contest ---

import { cardsMshFixture } from "./fixtures/cards-msh";

const P0P1_SLOT_KEYS: SlotKey[] = [
  "white_common", "blue_common", "black_common", "red_common",
  "green_common", "multicolor_uncommon", "wildcard_common", "wildcard_uncommon",
];

const p0p1Picks = new Map<string, P0P1Pick>();

// Seed mock picks with a mix of crowd-favorite, minority, and rogue picks
// (not the top card in every slot), and never the same card twice across
// slots - wildcard_common/wildcard_uncommon's filters are supersets of the
// color- and type-specific slots, so naive independent picks can collide,
// which the real ballot never allows. Slots are walked in P0P1_SLOT_KEYS
// order (wildcards last) so their picks can see what's already claimed.
{
  const statsBySlot = new Map<SlotKey, P0P1PickStat[]>();
  for (const stat of generateP0P1PickStats()) {
    const slotStats = statsBySlot.get(stat.slot);
    if (slotStats) slotStats.push(stat);
    else statsBySlot.set(stat.slot, [stat]);
  }

  const RANK_PATTERN: Array<"top" | "middle" | "bottom"> =
    ["top", "bottom", "middle", "top", "bottom", "middle", "top", "bottom"];
  const claimed = new Set<string>();

  P0P1_SLOT_KEYS.forEach((slot, i) => {
    const slotStats = statsBySlot.get(slot);
    if (!slotStats || slotStats.length === 0) return;
    const rank = RANK_PATTERN[i % RANK_PATTERN.length];
    const targetIndex = rank === "top" ? 0
      : rank === "bottom" ? slotStats.length - 1
      : Math.floor(slotStats.length / 2);
    for (let offset = 0; offset < slotStats.length; offset++) {
      const stat = slotStats[(targetIndex + offset) % slotStats.length];
      if (!claimed.has(stat.cardName)) {
        claimed.add(stat.cardName);
        p0p1Picks.set(slot, { slot, cardName: stat.cardName, lastUpdated: "2026-06-10T00:00:00Z" });
        break;
      }
    }
  });
}

export const fetchP0P1Cards = (_setCode: string): Promise<Card[]> =>
  wait(cardsMshFixture);

export const fetchP0P1Picks = (_setCode: string): Promise<P0P1Pick[]> =>
  wait([...p0p1Picks.values()]);

export const upsertP0P1Pick = async (
  _setCode: string,
  slot: SlotKey,
  cardName: string,
): Promise<void> => {
  p0p1Picks.set(slot, { slot, cardName, lastUpdated: new Date().toISOString() });
};


export const deleteAllP0P1Picks = async (
  _setCode: string,
): Promise<void> => {
  p0p1Picks.clear();
};

function forceTrailingTie(counts: number[], tieCount: number, value: number) {
  let surplus = 0;
  for (let i = counts.length - tieCount; i < counts.length; i++) {
    surplus += counts[i] - value;
    counts[i] = value;
  }
  counts[0] += surplus;
}

function generateP0P1PickStats(): P0P1PickStat[] {
  const stats: P0P1PickStat[] = [];
  const slotFilters: Record<string, (c: Card) => boolean> = {
    white_common: (c) => c.rarity === "common" && c.colors.length === 1 && c.colors[0] === "W",
    blue_common: (c) => c.rarity === "common" && c.colors.length === 1 && c.colors[0] === "U",
    black_common: (c) => c.rarity === "common" && c.colors.length === 1 && c.colors[0] === "B",
    red_common: (c) => c.rarity === "common" && c.colors.length === 1 && c.colors[0] === "R",
    green_common: (c) => c.rarity === "common" && c.colors.length === 1 && c.colors[0] === "G",
    multicolor_uncommon: (c) => c.rarity === "uncommon" && c.colors.length >= 2,
    wildcard_common: (c) => c.rarity === "common" && !c.typeLine.startsWith("Basic Land"),
    wildcard_uncommon: (c) => c.rarity === "uncommon",
  };
  let seed = 42;
  const rng = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
  const TOTAL_VOTERS = 87;

  for (const slotKey of P0P1_SLOT_KEYS) {
    const eligible = cardsMshFixture.filter(slotFilters[slotKey]);
    const count = Math.min(eligible.length, 3 + Math.floor(rng() * 6));
    const picked = eligible.slice(0, count);
    let remaining = TOTAL_VOTERS;
    const counts: number[] = [];
    for (let i = 0; i < picked.length; i++) {
      if (i === picked.length - 1) {
        counts.push(remaining);
      } else {
        const share = Math.max(1, Math.floor(remaining * (0.15 + rng() * 0.45)));
        counts.push(share);
        remaining -= share;
      }
    }
    counts.sort((a, b) => b - a);
    if (slotKey === "black_common" && counts.length >= 3) {
      forceTrailingTie(counts, 3, 4);
    }
    if (slotKey === "wildcard_common" && counts.length >= 4) {
      forceTrailingTie(counts, 4, 5);
    }
    for (let i = 0; i < picked.length; i++) {
      stats.push({
        setCode: "MSH",
        slot: slotKey,
        cardName: picked[i].name,
        pickCount: counts[i],
        pickPct: Math.round(counts[i] * 1000 / TOTAL_VOTERS) / 10,
      });
    }
  }
  return stats;
}

export const fetchP0P1PickStats = (_setCode: string): Promise<P0P1PickStat[]> => wait(generateP0P1PickStats());

export const initialAuthUser = {
  id: "mock-user-id",
  discordId: "123456789",
  username: "MockPlayer",
  avatarUrl: null,
};
