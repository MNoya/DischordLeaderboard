import { BUCKET_DEFS, type BucketDef } from "../data/format-buckets";
import type { PlayerFormatBreakdown } from "../types/leaderboard";

export interface BreakdownRow {
  label: string;
  played: boolean;
  events: number;
  wins: number;
  losses: number;
  count: number;
  points: number;
  rate: number;
  confidence: number | null;
  score: number;
}

export function pct(n: number): string {
  return `${Math.round(n * 100)}%`;
}

const FULL_FORMAT_NAMES: Record<string, string> = {
  Premier: "Premier Draft",
  Trad: "Traditional Draft",
  Sealed: "Sealed",
  Quick: "Quick Draft",
  "LCQ Draft 1": "LCQ Draft 1",
  "LCQ Draft 2": "LCQ Draft 2",
};

export function fullFormatName(label: string): string {
  return FULL_FORMAT_NAMES[label] ?? label;
}

function rowFor(def: BucketDef, breakdown: PlayerFormatBreakdown[]): BreakdownRow {
  const r = breakdown.find((b) => b.formatLabel === def.label);
  const events = r?.events ?? 0;
  const wins = r?.wins ?? 0;
  const losses = r?.losses ?? 0;
  const trophies = r?.trophies ?? 0;

  if (def.rule === "lcq_draft_2") {
    const games = wins + losses;
    const winrate = games > 0 ? wins / games : 0;
    const score = games > 0 && wins > 0 ? wins * winrate * def.points : 0;
    return {
      label: def.label,
      played: games > 0,
      events,
      wins,
      losses,
      count: wins,
      points: def.points,
      rate: winrate,
      confidence: null,
      score,
    };
  }

  const trophyRate = events > 0 ? trophies / events : 0;
  const confidence = trophies > 0 ? trophies / (trophies + 2) : 0;
  const score =
    trophies > 0 && events > 0 ? trophies * def.points * trophyRate * confidence : 0;
  return {
    label: def.label,
    played: events > 0,
    events,
    wins,
    losses,
    count: trophies,
    points: def.points,
    rate: trophyRate,
    confidence,
    score,
  };
}

export function computeRows(breakdown: PlayerFormatBreakdown[]): BreakdownRow[] {
  return BUCKET_DEFS.map((def) => rowFor(def, breakdown)).filter((r) => r.played);
}
