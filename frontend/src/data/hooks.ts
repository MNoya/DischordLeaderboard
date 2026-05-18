// Hook layer (spec §3) — abstracts the data source from components.
//
// Components import `useLeaderboard`, `usePlayerProfile`, etc; they never see
// fetch logic, fixtures, or supabase. Wired through TanStack Query so caching
// keys, stale-time, and idle prefetch sit in one place.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import {
  fetchAvailableFormats,
  fetchColorsLeaderboard,
  fetchColorsSummary,
  fetchFormatColorsLeaderboard,
  fetchFormatLeaderboard,
  fetchFormatRecentTrophies,
  fetchLeaderboard,
  fetchOtherColorsLeaderboard,
  fetchPlayerDraftEvents,
  fetchPlayerProfile,
  fetchPodEventParticipants,
  fetchPodEvents,
  fetchPodLeaderboard,
  fetchPodSetCodes,
  fetchRecentTrophies,
  fetchSets,
} from "./api";
import { MULTI, OTHER } from "./filters";
const FIVE_MINUTES = 5 * 60 * 1000;

export function useSets() {
  return useQuery({
    queryKey: ["sets"],
    queryFn: fetchSets,
    staleTime: FIVE_MINUTES,
  });
}

export function useAvailableFormats(setCode: string | undefined) {
  return useQuery({
    queryKey: ["available-formats", setCode],
    queryFn: () => fetchAvailableFormats(setCode!),
    enabled: !!setCode,
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

export function useColorsLeaderboard(
  setCode: string | undefined,
  colors: string | undefined
) {
  return useQuery({
    queryKey: ["colors-leaderboard", setCode, colors],
    queryFn: () => fetchColorsLeaderboard(setCode!, colors!),
    enabled: !!setCode && !!colors,
    staleTime: FIVE_MINUTES,
  });
}

export function useFormatColorsLeaderboard(
  setCode: string | undefined,
  format: string | undefined,
  archetypes: string | string[] | undefined,
) {
  const key = Array.isArray(archetypes) ? [...archetypes].sort().join(",") : archetypes;
  const enabled = !!setCode && !!format && !!archetypes
    && (Array.isArray(archetypes) ? archetypes.length > 0 : true);
  return useQuery({
    queryKey: ["format-colors-leaderboard", setCode, format, key],
    queryFn: () => fetchFormatColorsLeaderboard(setCode!, format!, archetypes!),
    enabled,
    staleTime: FIVE_MINUTES,
  });
}

export function useOtherColorsLeaderboard(
  setCode: string | undefined,
  otherCombos: string[] | undefined,
  formatFilter?: string,
) {
  const key = otherCombos ? [...otherCombos].sort().join(",") : null;
  return useQuery({
    queryKey: ["other-colors-leaderboard", setCode, key, formatFilter ?? null],
    queryFn: () => fetchOtherColorsLeaderboard(setCode!, otherCombos!, formatFilter),
    enabled: !!setCode && !!otherCombos && otherCombos.length > 0,
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

export function useColorsSummary(setCode: string | undefined) {
  return useQuery({
    queryKey: ["colors-summary", setCode],
    queryFn: () => fetchColorsSummary(setCode!),
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

// All trophies for the set filtered to a specific format. Backs both Top Colors
// and Recent Trophies in the sidebar when the user picks a format.
export function useFormatScopedTrophies(
  setCode: string | undefined,
  format: string | undefined,
) {
  return useQuery({
    queryKey: ["format-trophies", setCode, format],
    queryFn: () => fetchFormatRecentTrophies(setCode!, format!),
    enabled: !!setCode && !!format,
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

// Warm the cache for the top N players' profile + draft events. When a row is
// later expanded (or its profile page is opened), it renders instantly.
export function useIdlePrefetchTopPlayers(
  rows: ReadonlyArray<{ slug: string; setCode: string }> | undefined,
  limit = 25,
) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!rows || rows.length === 0) return;
    const top = rows.slice(0, limit);
    const handle = (window.requestIdleCallback ?? window.setTimeout)(() => {
      for (const r of top) {
        qc.prefetchQuery({
          queryKey: ["player-profile", r.slug, r.setCode],
          queryFn: () => fetchPlayerProfile(r.slug, r.setCode),
          staleTime: FIVE_MINUTES,
        });
        qc.prefetchQuery({
          queryKey: ["draft-events", r.slug, r.setCode],
          queryFn: () => fetchPlayerDraftEvents(r.slug, r.setCode),
          staleTime: FIVE_MINUTES,
        });
      }
    });
    return () => {
      if (typeof handle === "number") clearTimeout(handle);
      else window.cancelIdleCallback?.(handle as number);
    };
  }, [rows, qc, limit]);
}

// Builds the dynamic chip list for the colors filter: 2-color guilds + popular
// 3-color combos that pass the 1% threshold, then MULTI and OTHER catchalls.
// Returns the named chip list and the set of sub-threshold combos that get
// rolled into "OTHER".
export function useColorChips(setCode: string): { chips: string[]; otherCombos: string[] } {
  const { data } = useColorsSummary(setCode);
  return useMemo(() => {
    if (!data) return { chips: [], otherCombos: [] };
    const total = data
      .filter((r) => r.colors !== MULTI && r.colors !== "")
      .reduce((s, r) => s + r.events, 0);
    if (total === 0) return { chips: [], otherCombos: [] };
    const threshold = total * 0.01;
    const named: string[] = [];
    const otherCombos: string[] = [];
    for (const r of data) {
      if (r.colors === "" || r.colors === MULTI) continue;
      if (r.colors.length >= 4) continue;
      if (r.events >= threshold) named.push(r.colors);
      else otherCombos.push(r.colors);
    }
    const groupRank = (s: string) => (s.length === 2 ? 0 : s.length === 1 ? 1 : 2);
    named.sort((a, b) => {
      const ra = groupRank(a);
      const rb = groupRank(b);
      if (ra !== rb) return ra - rb;
      const ea = data.find((r) => r.colors === a)?.events ?? 0;
      const eb = data.find((r) => r.colors === b)?.events ?? 0;
      return eb - ea;
    });
    const chips: string[] = [...named];
    const hasMulti = data.some((r) => r.colors === MULTI && r.events > 0);
    if (hasMulti) chips.push(MULTI);
    if (otherCombos.length > 0) chips.push(OTHER);
    return { chips, otherCombos };
  }, [data]);
}


export function usePodEvents(setCode: string | undefined) {
  return useQuery({
    queryKey: ["pod-events", setCode],
    queryFn: () => fetchPodEvents(setCode!),
    enabled: !!setCode,
    staleTime: FIVE_MINUTES,
  });
}

export function usePodEventParticipants(eventId: string | undefined) {
  return useQuery({
    queryKey: ["pod-event-participants", eventId],
    queryFn: () => fetchPodEventParticipants(eventId!),
    enabled: !!eventId,
    staleTime: FIVE_MINUTES,
  });
}

export function usePodLeaderboard(setCode: string | undefined) {
  return useQuery({
    queryKey: ["pod-leaderboard", setCode],
    queryFn: () => fetchPodLeaderboard(setCode!),
    enabled: !!setCode,
    staleTime: FIVE_MINUTES,
  });
}

export function usePodSetCodes() {
  return useQuery({
    queryKey: ["pod-set-codes"],
    queryFn: fetchPodSetCodes,
    staleTime: FIVE_MINUTES,
  });
}
