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
