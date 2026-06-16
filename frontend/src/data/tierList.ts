import { useEffect, useState } from "react";
import { useQueries } from "@tanstack/react-query";
import {
  TIER_LIST_DATA_BASE,
  TIER_LIST_DATA_BASE_OVERRIDES,
  TIER_LIST_GRADERS,
  TIER_LIST_PREVIEW_SETS,
  TIER_LIST_UIDS,
} from "./constants";
import type { SetSummary } from "../types/leaderboard";

// A set has a tier list if it has a consensus list of its own or grader lists to compare.
export function hasTierList(code: string): boolean {
  return Boolean(TIER_LIST_UIDS[code]) || (TIER_LIST_GRADERS[code]?.length ?? 0) > 0;
}

// Sets that have a tier list (live feed or preview snapshot), newest first.
// The first entry is the latest available tier list.
export function buildTierListSets(sets: SetSummary[] | undefined): SetSummary[] {
  const live = (sets ?? []).filter((s) => hasTierList(s.code));
  const liveCodes = new Set(live.map((s) => s.code));
  const previews = Object.entries(TIER_LIST_PREVIEW_SETS)
    .filter(([code]) => hasTierList(code) && !liveCodes.has(code))
    .map(
      ([code, info]): SetSummary => ({
        code,
        name: info.name,
        startDate: info.startDate,
        endDate: "",
        isActive: false,
      }),
    );
  return [...previews, ...live].sort((a, b) => b.startDate.localeCompare(a.startDate));
}

export interface GraderGrade {
  name: string;
  tier: string;
}

export interface Grader {
  name: string;
  uid: string;
}

export const TIER_ORDER = [
  "A+",
  "A",
  "A-",
  "B+",
  "B",
  "B-",
  "C+",
  "C",
  "C-",
  "D+",
  "D",
  "D-",
  "F",
  "SB",
  "TBD",
];
export const COLOR_CODES = ["W", "U", "B", "R", "G", "M", "C", "L"];
export const COLOR_NAMES = [
  "White",
  "Blue",
  "Black",
  "Red",
  "Green",
  "Multicolor",
  "Colorless",
  "Land",
];

export interface TierCard {
  card_id: number;
  name: string;
  url: string;
  rarity: string;
  color: string;
  tier: string;
  sort_key: number | null;
  collector_number?: string | null;
  comment: string;
  types: string[];
  cmc: number;
  expansion: string;
  inclusion_type: string;
  flags: { buildaround: boolean; synergy: boolean; sideboard?: boolean };
  trend?: "up" | "down" | null;
  trend_from?: string | null;
  graders?: GraderGrade[];
}

export const TREND_COLOR: Record<"up" | "down", string> = {
  up: "#4ade80",
  down: "#f87171",
};
export const TREND_GLYPH: Record<"up" | "down", string> = { up: "▲", down: "▼" };
export const TREND_LABEL: Record<"up" | "down", string> = {
  up: "Up since the set review",
  down: "Down since the set review",
};

export function trendSteps(card: TierCard): number {
  if (!card.trend) return 0;
  const from = TIER_ORDER.indexOf(card.trend_from ?? "");
  const to = TIER_ORDER.indexOf(card.tier);
  if (from === -1 || to === -1) return 1;
  return Math.max(1, Math.abs(to - from));
}

// Filterable type groups — some card types collapse into one toggle (subtypes are ignored)
export const TYPE_GROUPS: Array<{
  key: string;
  label: string;
  ms: string;
  types: string[];
}> = [
  { key: "creature", label: "Creature", ms: "creature", types: ["creature"] },
  {
    key: "spell",
    label: "Instant / Sorcery",
    ms: "instant",
    types: ["instant", "sorcery"],
  },
  {
    key: "permanent",
    label: "Artifact / Enchantment / Planeswalker",
    ms: "enchantment",
    types: ["artifact", "enchantment", "planeswalker"],
  },
  { key: "battle", label: "Battle", ms: "battle", types: ["battle"] },
  { key: "land", label: "Land", ms: "land", types: ["land"] },
];
const TYPE_GROUP_BY_KEY: Record<string, { types: string[] }> =
  Object.fromEntries(TYPE_GROUPS.map((g) => [g.key, g]));

export const MANA_VALUE_BUCKETS = ["1", "2", "3", "4", "5", "6+"];

export function manaValueBucket(cmc: number): string {
  const n = Math.floor(cmc);
  return n >= 6 ? "6+" : String(n);
}

// Each group is an OR within itself and AND across groups; empty group = no constraint
export interface TierFilters {
  sets: string[];
  manaValues: string[];
  rarities: string[];
  cardTypes: string[];
  trends: string[];
}

export const EMPTY_FILTERS: TierFilters = {
  sets: [],
  manaValues: [],
  rarities: [],
  cardTypes: [],
  trends: [],
};

export function hasActiveFilters(f: TierFilters): boolean {
  return (
    f.sets.length > 0 ||
    f.manaValues.length > 0 ||
    f.rarities.length > 0 ||
    f.cardTypes.length > 0 ||
    f.trends.length > 0
  );
}

// Selecting both trends keeps unchanged cards visible but dimmed (isCardTrendDimmed)
function cardMatchesFilters(card: TierCard, f: TierFilters): boolean {
  if (f.trends.length === 1 && card.trend !== f.trends[0]) return false;
  if (f.sets.length > 0 && !f.sets.includes(card.expansion)) return false;
  if (
    f.manaValues.length > 0 &&
    !f.manaValues.includes(manaValueBucket(card.cmc))
  )
    return false;
  if (f.rarities.length > 0 && !f.rarities.includes(card.rarity)) return false;
  if (f.cardTypes.length > 0) {
    const present = new Set(card.types.map((t) => t.toLowerCase()));
    const inSelectedGroup = f.cardTypes.some((key) =>
      TYPE_GROUP_BY_KEY[key]?.types.some((t) => present.has(t)),
    );
    if (!inSelectedGroup) return false;
  }
  return true;
}

export function isCardFilteredOut(card: TierCard, f: TierFilters): boolean {
  if (!hasActiveFilters(f)) return false;
  return !cardMatchesFilters(card, f);
}

export function isCardTrendDimmed(card: TierCard, f: TierFilters): boolean {
  return f.trends.length === 2 && !card.trend;
}

export const RARITY_ORDER = ["C", "U", "R", "M"];
export const RARITY_NAMES: Record<string, string> = {
  C: "Common",
  U: "Uncommon",
  R: "Rare",
  M: "Mythic",
};

const INCLUSION_ORDER = ["Main Set", "Bonus Sheet", "Special Guests"];

export interface TierFilterOptions {
  sets: Array<{ value: string; label: string; count: number }>;
  rarities: Array<{ value: string; name: string; count: number }>;
  types: Array<{ value: string; label: string; ms: string; count: number }>;
  trends: { up: number; down: number };
}

export function tierFilterOptions(cards: TierCard[]): TierFilterOptions {
  const setInfo = new Map<string, { label: string; count: number }>();
  const rarityCounts = new Map<string, number>();
  const groupCounts = new Map<string, number>();
  const trendCounts = { up: 0, down: 0 };
  for (const card of cards) {
    if (card.trend) {
      trendCounts[card.trend] += 1;
    }
    const set = setInfo.get(card.expansion);
    if (set) {
      set.count += 1;
    } else {
      setInfo.set(card.expansion, { label: card.inclusion_type, count: 1 });
    }
    rarityCounts.set(card.rarity, (rarityCounts.get(card.rarity) ?? 0) + 1);
    const present = new Set(card.types.map((t) => t.toLowerCase()));
    for (const group of TYPE_GROUPS) {
      if (group.types.some((t) => present.has(t))) {
        groupCounts.set(group.key, (groupCounts.get(group.key) ?? 0) + 1);
      }
    }
  }
  const sets = [...setInfo.entries()]
    .map(([value, { label, count }]) => ({ value, label, count }))
    .sort((a, b) => {
      const ra = INCLUSION_ORDER.indexOf(a.label);
      const rb = INCLUSION_ORDER.indexOf(b.label);
      return (
        (ra === -1 ? INCLUSION_ORDER.length : ra) -
        (rb === -1 ? INCLUSION_ORDER.length : rb)
      );
    });
  return {
    sets,
    rarities: RARITY_ORDER.filter((r) => rarityCounts.has(r)).map((r) => ({
      value: r,
      name: RARITY_NAMES[r],
      count: rarityCounts.get(r)!,
    })),
    types: TYPE_GROUPS.filter((g) => groupCounts.has(g.key)).map((g) => ({
      value: g.key,
      label: g.label,
      ms: g.ms,
      count: groupCounts.get(g.key)!,
    })),
    trends: trendCounts,
  };
}

const HIDE_ART_STORAGE_KEY = "tierListHideArt";

export function useHideArt(): [boolean, (value: boolean) => void] {
  const [hideArt, setHideArt] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(HIDE_ART_STORAGE_KEY) === "1";
  });
  useEffect(() => {
    window.localStorage.setItem(HIDE_ART_STORAGE_KEY, hideArt ? "1" : "0");
  }, [hideArt]);
  return [hideArt, setHideArt];
}

const ONE_HOUR = 60 * 60 * 1000;

const normalizeName = (name: string) => name.trim().toLowerCase();

interface TierListPayload {
  cards: TierCard[];
  lastUpdated: string | null;
}

// Bare-array responses are card ratings only; the dict shape adds list metadata
// including `last_updated` (UTC, space-separated).
async function fetchTierList(uid: string): Promise<TierListPayload> {
  const override = TIER_LIST_DATA_BASE_OVERRIDES[uid];
  const res = await fetch(override ?? `${TIER_LIST_DATA_BASE}/${uid}`);
  if (!res.ok) {
    throw new Error(`Tier list fetch failed: ${res.status}`);
  }
  const json = await res.json();
  if (Array.isArray(json)) {
    return { cards: json, lastUpdated: null };
  }
  const lastUpdated = json?.last_updated
    ? `${String(json.last_updated).replace(" ", "T")}Z`
    : null;
  return { cards: json?.ratings ?? [], lastUpdated };
}

// The consensus list updates every few days; grader review lists are locked and never change,
// so they cache forever and the join attaches each grader's grade onto its card by name.
export function useTierList(uid: string | undefined, graders: Grader[] = []) {
  const results = useQueries({
    queries: [
      {
        queryKey: ["tier-list", uid],
        queryFn: () => fetchTierList(uid!),
        enabled: !!uid,
        staleTime: ONE_HOUR,
      },
      ...graders.map((grader) => ({
        queryKey: ["tier-list", grader.uid],
        queryFn: () => fetchTierList(grader.uid),
        staleTime: Infinity,
        gcTime: Infinity,
      })),
    ],
  });

  const [consensus, ...graderResults] = results;
  let data = consensus.data?.cards;
  if (data && graders.length > 0) {
    const gradesByName = graderResults.map((result) => {
      const byName = new Map<string, string>();
      for (const card of result.data?.cards ?? []) {
        byName.set(normalizeName(card.name), card.tier);
      }
      return byName;
    });
    data = data.map((card) => ({
      ...card,
      graders: graders
        .map((grader, i) => ({
          name: grader.name,
          tier: gradesByName[i].get(normalizeName(card.name)),
        }))
        .filter((grade): grade is GraderGrade => Boolean(grade.tier)),
    }));
  }

  return {
    data,
    lastUpdated: consensus.data?.lastUpdated ?? null,
    isLoading: consensus.isLoading,
    isError: consensus.isError,
  };
}
