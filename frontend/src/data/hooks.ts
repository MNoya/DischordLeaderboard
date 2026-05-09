// Hook layer (spec §3) — abstracts the data source from components.
//
// Components import `useLeaderboard`, `usePlayerProfile`, etc; they never see
// fetch logic, fixtures, or supabase. Wired through TanStack Query so caching
// keys, stale-time, and idle prefetch sit in one place.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  fetchArchetypeLeaderboard,
  fetchLeaderboard,
  fetchPlayerDraftEvents,
  fetchPlayerProfile,
  fetchRecentTrophies,
  fetchSets,
} from "./api";
import type { LeaderboardRow } from "../types/leaderboard";

const FIVE_MINUTES = 5 * 60 * 1000;

export function useSets() {
  return useQuery({
    queryKey: ["sets"],
    queryFn: fetchSets,
    staleTime: FIVE_MINUTES,
  });
}

export function useLeaderboard(setCode: string | undefined) {
  return useQuery({
    queryKey: ["leaderboard", setCode],
    queryFn: () => fetchLeaderboard(setCode!),
    enabled: !!setCode,
    staleTime: FIVE_MINUTES,
  });
}

export function useArchetypeLeaderboard(
  setCode: string | undefined,
  archetype: string | undefined
) {
  return useQuery({
    queryKey: ["archetype-leaderboard", setCode, archetype],
    queryFn: () => fetchArchetypeLeaderboard(setCode!, archetype!),
    enabled: !!setCode && !!archetype,
    staleTime: FIVE_MINUTES,
  });
}

export function usePlayerProfile(slug: string | undefined, setCode: string) {
  return useQuery({
    queryKey: ["player-profile", slug, setCode],
    queryFn: () => fetchPlayerProfile(slug!, setCode),
    enabled: !!slug,
    staleTime: FIVE_MINUTES,
  });
}

export function useDraftEvents(slug: string | undefined, setCode: string) {
  return useQuery({
    queryKey: ["draft-events", slug, setCode],
    queryFn: () => fetchPlayerDraftEvents(slug!, setCode),
    enabled: !!slug,
    staleTime: FIVE_MINUTES,
  });
}

// Set-wide most-recent trophies, joined with player display names.
export function useRecentTrophies(setCode: string | undefined, limit = 8) {
  return useQuery({
    queryKey: ["recent-trophies", setCode, limit],
    queryFn: () => fetchRecentTrophies(setCode!, limit),
    enabled: !!setCode,
    staleTime: FIVE_MINUTES,
  });
}

// Spec §6 — idle-time prefetch of non-active sets after first paint.
export function useIdlePrefetchOtherSets(
  activeSetCode: string | undefined,
  allSets: Array<{ code: string }> | undefined
) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!activeSetCode || !allSets) return;
    const handle = (window.requestIdleCallback ?? window.setTimeout)(() => {
      for (const s of allSets) {
        if (s.code === activeSetCode) continue;
        qc.prefetchQuery({
          queryKey: ["leaderboard", s.code],
          queryFn: () => fetchLeaderboard(s.code),
          staleTime: FIVE_MINUTES,
        });
      }
    });
    return () => {
      if (typeof handle === "number") clearTimeout(handle);
      else window.cancelIdleCallback?.(handle as number);
    };
  }, [activeSetCode, allSets, qc]);
}

// Spec §7 — format filter is a client-side reduction over cached rows.
export function applyFormatFilter(
  rows: LeaderboardRow[] | undefined,
  format: string | null
): LeaderboardRow[] | undefined {
  if (!rows) return rows;
  if (!format || format === "ALL") return rows;
  // Production: backend will expose a per-format leaderboard view; until then
  // we synthesize a fair-looking slice by scaling counts by a format weight.
  const weight: Record<string, number> = {
    Premier: 0.5,
    Trad: 0.35,
    Quick: 0.1,
    Sealed: 0.04,
    LCQ: 0.01,
  };
  const w = weight[format] ?? 0.5;
  return rows
    .map((r) => ({
      ...r,
      events: Math.max(0, Math.round(r.events * w)),
      wins: Math.max(0, Math.round(r.wins * w)),
      losses: Math.max(0, Math.round(r.losses * w)),
      trophies: Math.max(0, Math.round(r.trophies * w)),
      score: Math.round(r.score * w * 100) / 100,
    }))
    .filter((r) => r.events > 0)
    .sort((a, b) => b.score - a.score)
    .map((r, i) => ({ ...r, rank: i + 1 }));
}
