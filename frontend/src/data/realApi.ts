// Real-Supabase fetchers. Mirror of mockApi.ts function signatures — the hook
// layer picks one or the other via api.ts based on whether VITE_SUPABASE_URL
// is set.
//
// Each function reads from a curated public_* view (frontend-spec.md → Data
// contract). The adapter converts snake_case rows to camelCase. The anon key
// only has SELECT on these views; base tables stay locked under RLS.

import { supabase } from "./supabase";
import {
  adaptArchetypeRow,
  adaptDraftEvent,
  adaptFormatBreakdown,
  adaptLeaderboardRow,
  adaptSet,
} from "./adapter";
import type {
  ArchetypeLeaderboardRow,
  ArchetypeSummary,
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
  const [breakdown, leaderboard] = await Promise.all([
    client()
      .from("public_player_format_breakdown")
      .select("*")
      .eq("set_code", setCode)
      .eq("format_label", format),
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

  const rows = (breakdown.data ?? [])
    .map((raw) => raw as Record<string, unknown>)
    .filter((r) => {
      // Drop rows with zero events (the per-format breakdown view doesn't filter
      // them server-side) and rows whose player isn't on the leaderboard
      const events = (r.events as number) ?? 0;
      return events > 0 && info.has(r.slug as string);
    })
    .map((r) => {
      const inf = info.get(r.slug as string)!;
      return {
        setCode,
        slug: r.slug as string,
        displayName: inf.display_name as string,
        avatarUrl: (inf.avatar_url ?? null) as string | null,
        rank: 0, // assigned after sort
        score: Number(r.score_contribution ?? 0),
        trophies: r.trophies as number,
        events: r.events as number,
        wins: r.wins as number,
        losses: r.losses as number,
        lastCalculatedAt: inf.last_calculated_at as string,
      } satisfies LeaderboardRow;
    })
    .sort((a, b) => b.score - a.score)
    .map((r, i) => ({ ...r, rank: i + 1 }));

  return rows;
}

// ─── archetype summary (top archetypes by trophies, set-wide) ──────────────
// Aggregates public_archetype_leaderboard rows across all players. Each row
// in that view is one (player, set, archetype) cell, so summing trophies and
// counting rows per archetype gives us totals + player counts for free.

export async function fetchArchetypeSummary(setCode: string): Promise<ArchetypeSummary[]> {
  const { data, error } = await client()
    .from("public_archetype_leaderboard")
    .select("archetype, trophies, events")
    .eq("set_code", setCode);
  if (error) throw error;

  const agg = new Map<string, { trophies: number; events: number; players: number }>();
  for (const r of (data ?? []) as Array<Record<string, unknown>>) {
    const a = r.archetype as string;
    const cur = agg.get(a) ?? { trophies: 0, events: 0, players: 0 };
    cur.trophies += (r.trophies as number) ?? 0;
    cur.events += (r.events as number) ?? 0;
    cur.players += 1; // each row is a unique (player, archetype)
    agg.set(a, cur);
  }
  return Array.from(agg.entries())
    .map(([archetype, v]) => ({ setCode, archetype, ...v }))
    .filter((r) => r.trophies > 0)
    .sort((a, b) => b.trophies - a.trophies);
}

// ─── public_archetype_leaderboard ──────────────────────────────────────────

export async function fetchArchetypeLeaderboard(
  setCode: string,
  archetype: string,
): Promise<ArchetypeLeaderboardRow[]> {
  const { data, error } = await client()
    .from("public_archetype_leaderboard")
    .select("*")
    .eq("set_code", setCode)
    .eq("archetype", archetype)
    .order("rank", { ascending: true });
  if (error) throw error;
  return (data ?? []).map((r) => adaptArchetypeRow(r as Record<string, unknown>));
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
  // RecentTrophy is camelCase already in our spec; reuse the camelify pattern.
  return (data ?? []).map((r) => {
    const row = r as Record<string, unknown>;
    return {
      setCode: row.set_code as string,
      slug: row.slug as string,
      displayName: row.display_name as string,
      avatarUrl: (row.avatar_url ?? null) as string | null,
      format: row.format as string,
      colors: row.colors as string,
      wins: row.wins as number,
      losses: row.losses as number,
      finishedAt: row.finished_at as string,
    };
  });
}
