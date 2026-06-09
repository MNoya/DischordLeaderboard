import { useQuery } from "@tanstack/react-query";
import { TIER_LIST_DATA_BASE, TIER_LIST_DATA_BASE_OVERRIDES } from "./constants";

export const TIER_ORDER = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F", "SB", "TBD"];
export const COLOR_CODES = ["W", "U", "B", "R", "G", "M", "C", "L"];
export const COLOR_NAMES = ["White", "Blue", "Black", "Red", "Green", "Multicolor", "Colorless", "Land"];

export interface TierCard {
  card_id: number;
  name: string;
  url: string;
  rarity: string;
  color: string;
  tier: string;
  sort_key: number | null;
  comment: string;
  types: string[];
  cmc: number;
  expansion: string;
  inclusion_type: string;
  flags: { buildaround: boolean; synergy: boolean; sideboard?: boolean };
}

// Filterable type groups — some card types collapse into one toggle (subtypes are ignored)
export const TYPE_GROUPS: Array<{ key: string; label: string; ms: string; types: string[] }> = [
  { key: "creature", label: "Creature", ms: "creature", types: ["creature"] },
  { key: "spell", label: "Instant / Sorcery", ms: "instant", types: ["instant", "sorcery"] },
  {
    key: "permanent",
    label: "Artifact / Enchantment / Planeswalker",
    ms: "enchantment",
    types: ["artifact", "enchantment", "planeswalker"],
  },
  { key: "battle", label: "Battle", ms: "battle", types: ["battle"] },
  { key: "land", label: "Land", ms: "land", types: ["land"] },
];
const TYPE_GROUP_BY_KEY: Record<string, { types: string[] }> = Object.fromEntries(
  TYPE_GROUPS.map((g) => [g.key, g]),
);

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
}

export const EMPTY_FILTERS: TierFilters = { sets: [], manaValues: [], rarities: [], cardTypes: [] };

export function hasActiveFilters(f: TierFilters): boolean {
  return f.sets.length > 0 || f.manaValues.length > 0 || f.rarities.length > 0 || f.cardTypes.length > 0;
}

function cardMatchesFilters(card: TierCard, f: TierFilters): boolean {
  if (f.sets.length > 0 && !f.sets.includes(card.expansion)) return false;
  if (f.manaValues.length > 0 && !f.manaValues.includes(manaValueBucket(card.cmc))) return false;
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

export const RARITY_ORDER = ["C", "U", "R", "M"];
export const RARITY_NAMES: Record<string, string> = { C: "Common", U: "Uncommon", R: "Rare", M: "Mythic" };

const INCLUSION_ORDER = ["Main Set", "Bonus Sheet", "Special Guests"];

export interface TierFilterOptions {
  sets: Array<{ value: string; label: string; count: number }>;
  rarities: Array<{ value: string; name: string; count: number }>;
  types: Array<{ value: string; label: string; ms: string; count: number }>;
}

export function tierFilterOptions(cards: TierCard[]): TierFilterOptions {
  const setInfo = new Map<string, { label: string; count: number }>();
  const rarityCounts = new Map<string, number>();
  const groupCounts = new Map<string, number>();
  for (const card of cards) {
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
      return (ra === -1 ? INCLUSION_ORDER.length : ra) - (rb === -1 ? INCLUSION_ORDER.length : rb);
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
  };
}

const FIVE_MINUTES = 5 * 60 * 1000;

async function fetchTierList(uid: string): Promise<TierCard[]> {
  const base = TIER_LIST_DATA_BASE_OVERRIDES[uid] ?? TIER_LIST_DATA_BASE;
  const res = await fetch(`${base}/${uid}`);
  if (!res.ok) {
    throw new Error(`Tier list fetch failed: ${res.status}`);
  }
  const json = await res.json();
  return Array.isArray(json) ? json : (json?.ratings ?? []);
}

export function useTierList(uid: string | undefined) {
  return useQuery({
    queryKey: ["tier-list", uid],
    queryFn: () => fetchTierList(uid!),
    enabled: !!uid,
    staleTime: FIVE_MINUTES,
  });
}
