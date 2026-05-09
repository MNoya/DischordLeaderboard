// Hook layer (spec §3) — abstracts the data source from components.
//
// Components import `useLeaderboard`, `usePlayerProfile`, etc; they never see
// fetch logic, fixtures, or supabase. Wired through TanStack Query so caching
// keys, stale-time, and idle prefetch sit in one place.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  fetchArchetypeLeaderboard,
  fetchArchetypeSummary,
  fetchFormatLeaderboard,
  fetchLeaderboard,
  fetchPlayerDraftEvents,
  fetchPlayerProfile,
  fetchRecentTrophies,
  fetchSets,
} from "./api";
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

// Per-format leaderboard — switches data source from public_leaderboard to a
// join over public_player_format_breakdown when a format is selected. Returns
// the same row shape so the rendering table doesn't care which is live.
export function useFormatLeaderboard(
  setCode: string | undefined,
  format: string | undefined,
) {
  return useQuery({
    queryKey: ["format-leaderboard", setCode, format],
    queryFn: () => fetchFormatLeaderboard(setCode!, format!),
    enabled: !!setCode && !!format,
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

// Set-wide top archetypes, aggregated from public_archetype_leaderboard.
export function useArchetypeSummary(setCode: string | undefined) {
  return useQuery({
    queryKey: ["archetype-summary", setCode],
    queryFn: () => fetchArchetypeSummary(setCode!),
    enabled: !!setCode,
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

