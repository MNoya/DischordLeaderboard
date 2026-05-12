// Real-Supabase fetchers. Mirror of mockApi.ts function signatures — the hook
// layer picks one or the other via api.ts based on whether VITE_SUPABASE_URL
// is set.
//
// Each function reads from a curated public_* view (frontend-spec.md → Data
// contract). The adapter converts snake_case rows to camelCase. The anon key
// only has SELECT on these views; base tables stay locked under RLS.

import { supabase } from "./supabase";
import {
  adaptColorsRow,
  adaptDraftEvent,
  adaptFormatBreakdown,
  adaptLeaderboardRow,
  adaptSet,
} from "./adapter";
import { computeScore, type ScoringStatRow } from "./scoring";
import { colorsOf, effectiveColorCount } from "./utils";
import { FORMAT_LABEL_GROUPS, FORMAT_RAW_GROUPS } from "./filters";
import type {
  ColorsLeaderboardRow,
  ColorsSummary,
  LeaderboardRow,
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerProfile,
  RecentTrophy,
  SetSummary,
} from "../types/leaderboard";

function client() {
  if (!supabase) throw new Error("Supabase client is not configured");
  return supabase;
}

// ─── public_sets ───────────────────────────────────────────────────────────

export async function fetchSets(): Promise<SetSummary[]> {
  const { data, error } = await client()
    .from("public_sets")
    .select("*")
    .order("start_date", { ascending: false });
  if (error) throw error;
  return (data ?? []).map((r) => adaptSet(r as Record<string, unknown>));
}

export async function fetchFormatColorsLeaderboard(
  setCode: string,
  format: string,
  archetypes: string | string[],
): Promise<ColorsLeaderboardRow[]> {
  const labels = FORMAT_LABEL_GROUPS[format] ?? [format];
  const archs = Array.isArray(archetypes) ? archetypes : [archetypes];
  if (archs.length === 0) return [];
  const { data, error } = await client()
    .from("public_player_format_archetype_leaderboard")
    .select("*")
    .eq("set_code", setCode)
    .in("archetype", archs)
    .in("format_label", labels);
  if (error) throw error;
  // Aggregate per player (LCQ splits into two labels)
  const agg = new Map<string, ColorsLeaderboardRow>();
  for (const r of (data ?? [])) {
    const row = adaptColorsRow(r as Record<string, unknown>);
    const prev = agg.get(row.slug);
    if (!prev) {
      agg.set(row.slug, row);
    } else {
      prev.score += row.score;
      prev.trophies += row.trophies;
      prev.events += row.events;
      prev.wins += row.wins;
      prev.losses += row.losses;
    }
  }
  return Array.from(agg.values())
    .filter((r) => r.events > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const wpA = a.wins / Math.max(1, a.wins + a.losses);
      const wpB = b.wins / Math.max(1, b.wins + b.losses);
      if (wpB !== wpA) return wpB - wpA;
      return a.slug.localeCompare(b.slug);
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

export async function fetchAvailableFormats(setCode: string): Promise<string[]> {
  const { data, error } = await client()
    .from("public_player_format_breakdown")
    .select("format_label")
    .eq("set_code", setCode);
  if (error) throw error;
  return Array.from(new Set((data ?? []).map((r) => (r as { format_label: string }).format_label)));
}

// ─── public_leaderboard ────────────────────────────────────────────────────

export async function fetchLeaderboard(setCode: string): Promise<LeaderboardRow[]> {
  const { data, error } = await client()
    .from("public_leaderboard")
    .select("*")
    .eq("set_code", setCode)
    .order("rank", { ascending: true });
  if (error) throw error;
  return (data ?? []).map((r) => adaptLeaderboardRow(r as Record<string, unknown>));
}

// ─── per-format leaderboard ────────────────────────────────────────────────
// No dedicated view yet — we client-side join public_player_format_breakdown
// (filtered to format_label, sorted by score_contribution) with the leaderboard
// rows for displayName / avatarUrl / lastCalculatedAt. Players without any
// events in this format simply don't appear.

export async function fetchFormatLeaderboard(
  setCode: string,
  format: string,
): Promise<LeaderboardRow[]> {
  const labels = FORMAT_LABEL_GROUPS[format] ?? [format];
  const [breakdown, leaderboard] = await Promise.all([
    client()
      .from("public_player_format_breakdown")
      .select("*")
      .eq("set_code", setCode)
      .in("format_label", labels),
    client()
      .from("public_leaderboard")
      .select("slug, display_name, avatar_url, last_calculated_at")
      .eq("set_code", setCode),
  ]);
  if (breakdown.error) throw breakdown.error;
  if (leaderboard.error) throw leaderboard.error;

  const info = new Map(
    (leaderboard.data ?? []).map((r) => [
      (r as Record<string, unknown>).slug as string,
      r as Record<string, unknown>,
    ]),
  );

  const agg = new Map<string, LeaderboardRow>();
  for (const raw of breakdown.data ?? []) {
    const r = raw as Record<string, unknown>;
    const slug = r.slug as string;
    const events = (r.events as number) ?? 0;
    if (events <= 0 || !info.has(slug)) continue;
    const inf = info.get(slug)!;
    const cur = agg.get(slug);
    if (!cur) {
      agg.set(slug, {
        setCode,
        slug,
        displayName: inf.display_name as string,
        avatarUrl: (inf.avatar_url ?? null) as string | null,
        rank: 0,
        score: Number(r.score_contribution ?? 0),
        trophies: (r.trophies as number) ?? 0,
        events,
        wins: (r.wins as number) ?? 0,
        losses: (r.losses as number) ?? 0,
        lastCalculatedAt: inf.last_calculated_at as string,
      });
    } else {
      cur.score += Number(r.score_contribution ?? 0);
      cur.trophies += (r.trophies as number) ?? 0;
      cur.events += events;
      cur.wins += (r.wins as number) ?? 0;
      cur.losses += (r.losses as number) ?? 0;
    }
  }

  return Array.from(agg.values())
    .sort((a, b) => b.score - a.score)
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

export async function fetchColorsSummary(setCode: string): Promise<ColorsSummary[]> {
  const { data, error } = await client()
    .from("public_archetype_leaderboard")
    .select("archetype, trophies, events")
    .eq("set_code", setCode);
  if (error) throw error;

  const agg = new Map<string, { trophies: number; events: number; players: number }>();
  for (const r of (data ?? []) as Array<Record<string, unknown>>) {
    const c = r.archetype as string;
    const cur = agg.get(c) ?? { trophies: 0, events: 0, players: 0 };
    cur.trophies += (r.trophies as number) ?? 0;
    cur.events += (r.events as number) ?? 0;
    cur.players += 1;
    agg.set(c, cur);
  }
  return Array.from(agg.entries())
    .map(([colors, v]) => ({ setCode, colors, ...v }))
    .sort((a, b) => b.trophies - a.trophies);
}

export async function fetchColorsLeaderboard(
  setCode: string,
  colors: string,
): Promise<ColorsLeaderboardRow[]> {
  const { data, error } = await client()
    .from("public_archetype_leaderboard")
    .select("*")
    .eq("set_code", setCode)
    .eq("archetype", colors);
  if (error) throw error;
  return (data ?? [])
    .map((r) => adaptColorsRow(r as Record<string, unknown>))
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const wpA = a.wins / Math.max(1, a.wins + a.losses);
      const wpB = b.wins / Math.max(1, b.wins + b.losses);
      if (wpB !== wpA) return wpB - wpA;
      return a.slug.localeCompare(b.slug);
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

// OTHER aggregates raw events client-side because the archetype rollup also
// counts splash-into-MULTI trophies under their main archetype, which would
// double-count them into the OTHER bucket. By walking events directly we can
// enforce "main archetype is sub-threshold AND effective < 4" — keeping OTHER
// and SOUP exclusive — at the cost of fetching the set's full event stream.
export async function fetchOtherColorsLeaderboard(
  setCode: string,
  otherCombos: string[],
  formatFilter?: string,
): Promise<ColorsLeaderboardRow[]> {
  if (otherCombos.length === 0) return [];
  const otherSet = new Set(otherCombos);
  const formatGroup = formatFilter
    ? (FORMAT_RAW_GROUPS[formatFilter] ?? [formatFilter])
    : null;
  const formatAllowed = formatGroup ? new Set(formatGroup) : null;

  // Supabase caps each request at db-max-rows (default 1000). Page until done.
  const allEvents: Array<Record<string, unknown>> = [];
  const pageSize = 1000;
  for (let from = 0; ; from += pageSize) {
    const { data, error } = await client()
      .from("public_player_draft_events")
      .select("slug, format, colors, wins, losses, is_trophy, finished_at")
      .eq("set_code", setCode)
      .range(from, from + pageSize - 1);
    if (error) throw error;
    const batch = (data ?? []) as Array<Record<string, unknown>>;
    allEvents.push(...batch);
    if (batch.length < pageSize) break;
  }

  const metaResp = await client()
    .from("public_leaderboard")
    .select("slug, display_name, avatar_url, last_calculated_at")
    .eq("set_code", setCode);
  if (metaResp.error) throw metaResp.error;

  const metaBySlug = new Map<string, Record<string, unknown>>();
  for (const m of (metaResp.data ?? []) as Array<Record<string, unknown>>) {
    metaBySlug.set(m.slug as string, m);
  }

  interface PlayerAgg {
    formatRows: ScoringStatRow[];
    events: number;
    trophies: number;
    wins: number;
    losses: number;
    lastFinishedAt: string;
  }
  const perSlug = new Map<string, PlayerAgg>();

  for (const raw of allEvents) {
    const colors = (raw.colors as string | null) ?? "";
    if (effectiveColorCount(colors) >= 4) continue;
    if (!otherSet.has(colorsOf(colors))) continue;

    const slug = raw.slug as string;
    const fmt = (raw.format as string) ?? "";
    if (formatAllowed && !formatAllowed.has(fmt)) continue;
    const wins = (raw.wins as number) ?? 0;
    const losses = (raw.losses as number) ?? 0;
    const isTrophy = Boolean(raw.is_trophy);
    const finishedAt = (raw.finished_at as string) ?? "";

    let agg = perSlug.get(slug);
    if (!agg) {
      agg = { formatRows: [], events: 0, trophies: 0, wins: 0, losses: 0, lastFinishedAt: "" };
      perSlug.set(slug, agg);
    }
    agg.events += 1;
    agg.wins += wins;
    agg.losses += losses;
    if (isTrophy) agg.trophies += 1;
    agg.formatRows.push({ format: fmt, wins, losses, trophies: isTrophy ? 1 : 0, events: 1 });
    if (finishedAt > agg.lastFinishedAt) agg.lastFinishedAt = finishedAt;
  }

  const rows: ColorsLeaderboardRow[] = [];
  for (const [slug, agg] of perSlug) {
    if (agg.events === 0) continue;
    const meta = metaBySlug.get(slug);
    rows.push({
      setCode,
      colors: "OTHER",
      slug,
      displayName: (meta?.display_name as string) ?? slug,
      avatarUrl: (meta?.avatar_url as string | null) ?? null,
      rank: 0,
      score: computeScore(agg.formatRows),
      trophies: agg.trophies,
      events: agg.events,
      wins: agg.wins,
      losses: agg.losses,
      lastCalculatedAt:
        agg.lastFinishedAt ||
        ((meta?.last_calculated_at as string | undefined) ?? new Date(0).toISOString()),
    });
  }

  return rows
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const wpA = a.wins / Math.max(1, a.wins + a.losses);
      const wpB = b.wins / Math.max(1, b.wins + b.losses);
      if (wpB !== wpA) return wpB - wpA;
      return a.slug.localeCompare(b.slug);
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

// ─── public_player_format_breakdown + public_leaderboard composite ─────────

export async function fetchPlayerProfile(
  slug: string,
  setCode: string,
): Promise<PlayerProfile | null> {
  const [headlineResp, breakdownResp] = await Promise.all([
    client()
      .from("public_leaderboard")
      .select("*")
      .eq("set_code", setCode)
      .eq("slug", slug)
      .maybeSingle(),
    client()
      .from("public_player_format_breakdown")
      .select("*")
      .eq("set_code", setCode)
      .eq("slug", slug),
  ]);
  if (headlineResp.error) throw headlineResp.error;
  if (breakdownResp.error) throw breakdownResp.error;
  if (!headlineResp.data) return null;

  const headline = adaptLeaderboardRow(headlineResp.data as Record<string, unknown>);
  const breakdown = (breakdownResp.data ?? []).map((r) =>
    adaptFormatBreakdown(r as Record<string, unknown>),
  );
  return {
    slug: headline.slug,
    displayName: headline.displayName,
    avatarUrl: headline.avatarUrl,
    setCode: headline.setCode,
    rank: headline.rank,
    score: headline.score,
    trophies: headline.trophies,
    events: headline.events,
    wins: headline.wins,
    losses: headline.losses,
    formatBreakdown: breakdown,
  };
}

// ─── public_player_draft_events ────────────────────────────────────────────

export async function fetchPlayerDraftEvents(
  slug: string,
  setCode: string,
): Promise<PlayerDraftEvent[]> {
  const { data, error } = await client()
    .from("public_player_draft_events")
    .select("*")
    .eq("slug", slug)
    .eq("set_code", setCode)
    .order("finished_at", { ascending: false, nullsFirst: false });
  if (error) throw error;
  return (data ?? []).map((r) => adaptDraftEvent(r as Record<string, unknown>));
}

// ─── public_recent_trophies ────────────────────────────────────────────────

export async function fetchRecentTrophies(
  setCode: string,
  limit = 8,
): Promise<RecentTrophy[]> {
  const { data, error } = await client()
    .from("public_recent_trophies")
    .select("*")
    .eq("set_code", setCode)
    .order("finished_at", { ascending: false, nullsFirst: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []).map((r) => adaptRecentTrophy(r as Record<string, unknown>));
}

// Server-side format filter so the sidebar can rebuild Top Colors and Recent
// Trophies from a single dataset when the user picks a format. LCQ has compound
// raw labels; other formats substring-match (mirrors matchesFormatFilter).
export async function fetchFormatRecentTrophies(
  setCode: string,
  format: string,
): Promise<RecentTrophy[]> {
  const group = FORMAT_RAW_GROUPS[format];

  const all: RecentTrophy[] = [];
  const pageSize = 1000;
  for (let from = 0; ; from += pageSize) {
    let q = client()
      .from("public_recent_trophies")
      .select("*")
      .eq("set_code", setCode)
      .order("finished_at", { ascending: false, nullsFirst: false })
      .range(from, from + pageSize - 1);
    q = group ? q.in("format", group) : q.ilike("format", `%${format}%`);
    const { data, error } = await q;
    if (error) throw error;
    const batch = (data ?? []) as Array<Record<string, unknown>>;
    for (const row of batch) all.push(adaptRecentTrophy(row));
    if (batch.length < pageSize) break;
  }
  return all;
}

function adaptRecentTrophy(row: Record<string, unknown>): RecentTrophy {
  return {
    setCode: row.set_code as string,
    slug: row.slug as string,
    displayName: row.display_name as string,
    avatarUrl: (row.avatar_url ?? null) as string | null,
    seventeenlandsEventId: (row.seventeenlands_event_id ?? null) as string | null,
    format: row.format as string,
    colors: row.colors as string,
    wins: row.wins as number,
    losses: row.losses as number,
    finishedAt: row.finished_at as string,
  };
}
