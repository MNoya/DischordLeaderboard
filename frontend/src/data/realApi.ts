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
import { FORMAT_LABEL_GROUPS, FORMAT_RAW_GROUPS, MULTI, OTHER } from "./filters";
import type {
  ColorsLeaderboardRow,
  ColorsSummary,
  LeaderboardRow,
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerProfile,
  PodEventMatchRow,
  PodEventParticipantRow,
  PodEventReplayRow,
  PodEventSummary,
  PodLeaderboardRow,
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
  if (format === "Pod") {
    const arch = Array.isArray(archetypes) ? archetypes[0] : archetypes;
    return fetchPodColorsLeaderboard(setCode, arch, null);
  }
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
  const [breakdown, pod] = await Promise.all([
    client()
      .from("public_player_format_breakdown")
      .select("format_label")
      .eq("set_code", setCode),
    client()
      .from("public_player_pod_stats")
      .select("set_code", { count: "exact", head: true })
      .eq("set_code", setCode),
  ]);
  if (breakdown.error) throw breakdown.error;
  if (pod.error) throw pod.error;
  const labels = new Set(
    (breakdown.data ?? []).map((r) => (r as { format_label: string }).format_label),
  );
  if ((pod.count ?? 0) > 0) labels.add("Pod");
  return Array.from(labels);
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
  if (format === "Pod") {
    const rows = await fetchPodLeaderboard(setCode);
    return rows.map((r) => ({
      setCode: r.setCode,
      slug: r.slug,
      displayName: r.displayName,
      avatarUrl: r.avatarUrl,
      rank: r.rank,
      score: 0,
      trophies: r.trophies,
      events: r.events,
      wins: r.wins,
      losses: r.losses,
      lastCalculatedAt: r.lastFinishedAt ?? new Date(0).toISOString(),
    }));
  }
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
  if (formatFilter === "Pod") {
    return fetchPodColorsLeaderboard(setCode, OTHER, otherCombos);
  }
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
  if (format === "Pod") return fetchPodRecentTrophies(setCode);
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

export async function fetchPodEvents(setCode: string): Promise<PodEventSummary[]> {
  const { data, error } = await client()
    .from("public_pod_draft_events")
    .select("*")
    .eq("set_code", setCode)
    .order("event_time", { ascending: false });
  if (error) throw error;
  return (data ?? []).map((r) => adaptPodEvent(r as Record<string, unknown>));
}

export async function fetchPodEventParticipants(
  eventId: string,
): Promise<PodEventParticipantRow[]> {
  const { data, error } = await client()
    .from("public_pod_draft_event_participants")
    .select("*")
    .eq("event_id", eventId);
  if (error) throw error;
  return (data ?? []).map((r) => adaptPodEventParticipant(r as Record<string, unknown>));
}

export async function fetchPodEventBySlug(slug: string): Promise<PodEventSummary | null> {
  const { data, error } = await client()
    .from("public_pod_draft_events")
    .select("*")
    .eq("slug", slug)
    .maybeSingle();
  if (error) throw error;
  if (!data) return null;
  return adaptPodEvent(data as Record<string, unknown>);
}

export async function fetchPodEventMatches(eventId: string): Promise<PodEventMatchRow[]> {
  const { data, error } = await client()
    .from("public_pod_draft_event_matches")
    .select("*")
    .eq("event_id", eventId)
    .order("round", { ascending: true });
  if (error) throw error;
  return (data ?? []).map((r) => adaptPodEventMatch(r as Record<string, unknown>));
}

export async function fetchPodEventReplays(eventId: string): Promise<PodEventReplayRow[]> {
  const { data, error } = await client()
    .from("public_pod_draft_replays")
    .select("*")
    .eq("event_id", eventId)
    .order("game_time", { ascending: true });
  if (error) throw error;
  return (data ?? []).map((r) => adaptPodEventReplay(r as Record<string, unknown>));
}

interface PodParticipantParsed {
  eventId: string;
  finishedAt: string;
  slug: string | null;
  displayName: string;
  avatarUrl: string | null;
  deckColors: string | null;
  placement: number | null;
  wins: number;
  losses: number;
}

function parseRecord(record: string | null | undefined): { wins: number; losses: number } {
  const [w, l] = (record ?? "").split("-");
  return { wins: parseInt(w || "0", 10) || 0, losses: parseInt(l || "0", 10) || 0 };
}

async function fetchPodParticipantsForSet(setCode: string): Promise<PodParticipantParsed[]> {
  const eventsResp = await client()
    .from("public_pod_draft_events")
    .select("event_id, event_time")
    .eq("set_code", setCode);
  if (eventsResp.error) throw eventsResp.error;
  const eventTimeById = new Map<string, string>(
    ((eventsResp.data ?? []) as Array<{ event_id: string; event_time: string }>)
      .map((e) => [e.event_id, e.event_time]),
  );
  if (eventTimeById.size === 0) return [];

  const partsResp = await client()
    .from("public_pod_draft_event_participants")
    .select("event_id, player_slug, player_display_name, avatar_url, deck_colors, record, placement")
    .in("event_id", Array.from(eventTimeById.keys()));
  if (partsResp.error) throw partsResp.error;

  return (partsResp.data ?? []).map((raw) => {
    const r = raw as Record<string, unknown>;
    const slug = (r.player_slug as string | null) ?? null;
    return {
      eventId: r.event_id as string,
      finishedAt: eventTimeById.get(r.event_id as string) ?? "",
      slug,
      displayName: (r.player_display_name as string | null) ?? slug ?? "",
      avatarUrl: (r.avatar_url as string | null) ?? null,
      deckColors: (r.deck_colors as string | null) ?? null,
      placement: (r.placement as number | null) ?? null,
      ...parseRecord(r.record as string | null),
    };
  });
}

async function fetchPodRecentTrophies(setCode: string): Promise<RecentTrophy[]> {
  const parts = await fetchPodParticipantsForSet(setCode);
  return parts
    .filter((p) => p.placement === 1 && p.slug)
    .map((p) => ({
      setCode,
      slug: p.slug!,
      displayName: p.displayName,
      avatarUrl: p.avatarUrl,
      seventeenlandsEventId: null,
      format: "PodDraft",
      colors: p.deckColors ?? "",
      wins: p.wins,
      losses: p.losses,
      finishedAt: p.finishedAt,
    }))
    .sort((a, b) => (a.finishedAt < b.finishedAt ? 1 : a.finishedAt > b.finishedAt ? -1 : 0));
}

async function fetchPodColorsLeaderboard(
  setCode: string,
  colorsFilter: string,
  otherCombos: string[] | null,
): Promise<ColorsLeaderboardRow[]> {
  const parts = await fetchPodParticipantsForSet(setCode);
  const otherSet = otherCombos ? new Set(otherCombos) : null;
  const colorMatches = (deckColors: string | null): boolean => {
    if (!deckColors) return false;
    if (colorsFilter === MULTI) return effectiveColorCount(deckColors) >= 4;
    if (colorsFilter === OTHER) {
      if (effectiveColorCount(deckColors) >= 4) return false;
      return otherSet ? otherSet.has(colorsOf(deckColors)) : false;
    }
    return colorsOf(deckColors) === colorsFilter;
  };

  interface Agg {
    displayName: string;
    avatarUrl: string | null;
    events: number;
    wins: number;
    losses: number;
    trophies: number;
    lastFinishedAt: string;
  }
  const perSlug = new Map<string, Agg>();
  for (const p of parts) {
    if (p.placement === null || !p.slug || !colorMatches(p.deckColors)) continue;
    let agg = perSlug.get(p.slug);
    if (!agg) {
      agg = { displayName: p.displayName, avatarUrl: p.avatarUrl, events: 0, wins: 0, losses: 0, trophies: 0, lastFinishedAt: "" };
      perSlug.set(p.slug, agg);
    }
    agg.events += 1;
    agg.wins += p.wins;
    agg.losses += p.losses;
    if (p.placement === 1) agg.trophies += 1;
    if (p.finishedAt > agg.lastFinishedAt) agg.lastFinishedAt = p.finishedAt;
  }

  return Array.from(perSlug.entries())
    .map(([slug, a]) => ({
      setCode,
      colors: colorsFilter,
      slug,
      displayName: a.displayName,
      avatarUrl: a.avatarUrl,
      rank: 0,
      score: 0,
      trophies: a.trophies,
      events: a.events,
      wins: a.wins,
      losses: a.losses,
      lastCalculatedAt: a.lastFinishedAt || new Date(0).toISOString(),
    }))
    .sort((a, b) => {
      if (b.trophies !== a.trophies) return b.trophies - a.trophies;
      if (b.wins !== a.wins) return b.wins - a.wins;
      return a.slug.localeCompare(b.slug);
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

export async function fetchPodLeaderboard(setCode: string): Promise<PodLeaderboardRow[]> {
  const { data, error } = await client()
    .from("public_player_pod_stats")
    .select("*")
    .eq("set_code", setCode);
  if (error) throw error;
  return (data ?? [])
    .map((r) => adaptPodLeaderboardRow(r as Record<string, unknown>))
    .sort((a, b) => {
      if (b.trophies !== a.trophies) return b.trophies - a.trophies;
      if (b.wins !== a.wins) return b.wins - a.wins;
      return a.events - b.events;
    })
    .map((r, i) => ({ ...r, rank: i + 1 }));
}

export async function fetchPodSetCodes(): Promise<string[]> {
  const { data, error } = await client()
    .from("public_pod_draft_events")
    .select("set_code");
  if (error) throw error;
  const seen = new Set<string>();
  for (const r of data ?? []) seen.add((r as { set_code: string }).set_code);
  return Array.from(seen);
}

function adaptPodEvent(row: Record<string, unknown>): PodEventSummary {
  return {
    eventId: row.event_id as string,
    slug: row.slug as string,
    name: row.name as string,
    setCode: row.set_code as string,
    eventDate: row.event_date as string,
    eventTime: row.event_time as string,
    formatLabel: (row.format_label ?? null) as string | null,
    totalRounds: (row.total_rounds ?? 0) as number,
    championPlayerSlug: (row.champion_player_slug ?? null) as string | null,
    championDisplayName: (row.champion_display_name ?? null) as string | null,
    championAvatarUrl: (row.champion_avatar_url ?? null) as string | null,
    championDeckColors: (row.champion_deck_colors ?? null) as string | null,
    championRecord: (row.champion_record ?? null) as string | null,
    participantCount: (row.participant_count ?? 0) as number,
    isFinalized: (row.is_finalized ?? false) as boolean,
    discordEventId: (row.discord_event_id ?? null) as string | null,
  };
}

function adaptPodEventParticipant(row: Record<string, unknown>): PodEventParticipantRow {
  return {
    eventId: row.event_id as string,
    displayName: row.display_name as string,
    seatIndex: (row.seat_index ?? null) as number | null,
    placement: (row.placement ?? null) as number | null,
    record: (row.record ?? null) as string | null,
    deckColors: (row.deck_colors ?? null) as string | null,
    draftLogUrl: (row.draft_log_url ?? null) as string | null,
    deckScreenshotUrl: (row.deck_screenshot_url ?? null) as string | null,
    deckScreenshotCaption: (row.deck_screenshot_caption ?? null) as string | null,
    playerSlug: (row.player_slug ?? null) as string | null,
    playerDisplayName: (row.player_display_name ?? null) as string | null,
    avatarUrl: (row.avatar_url ?? null) as string | null,
  };
}

function adaptPodEventMatch(row: Record<string, unknown>): PodEventMatchRow {
  return {
    eventId: row.event_id as string,
    eventName: row.event_name as string,
    round: row.round as number,
    playerAName: row.player_a_name as string,
    playerBName: row.player_b_name as string,
    winnerName: (row.winner_name ?? null) as string | null,
    score: (row.score ?? null) as string | null,
    reportedAt: (row.reported_at ?? null) as string | null,
  };
}

function adaptPodEventReplay(row: Record<string, unknown>): PodEventReplayRow {
  return {
    eventId: row.event_id as string,
    eventName: row.event_name as string,
    eventDate: row.event_date as string,
    setCode: row.set_code as string,
    playerId: row.player_id as string,
    playerSlug: row.player_slug as string,
    playerDisplayName: row.player_display_name as string,
    gameId: row.game_id as string,
    link: row.link as string,
    gameTime: row.game_time as string,
    won: row.won as boolean,
    turns: (row.turns ?? null) as number | null,
    onPlay: (row.on_play ?? null) as boolean | null,
    inferredRound: (row.inferred_round ?? null) as number | null,
  };
}

function adaptPodLeaderboardRow(row: Record<string, unknown>): PodLeaderboardRow {
  return {
    setCode: row.set_code as string,
    rank: 0,
    slug: row.slug as string,
    displayName: row.display_name as string,
    avatarUrl: (row.avatar_url ?? null) as string | null,
    events: (row.events ?? 0) as number,
    wins: (row.wins ?? 0) as number,
    losses: (row.losses ?? 0) as number,
    trophies: (row.trophies ?? 0) as number,
    lastFinishedAt: (row.last_finished_at ?? null) as string | null,
  };
}
