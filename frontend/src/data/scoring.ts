// Formula port of bot/scoring.py — must stay in sync. Buckets + points come
// from the shared scoring_buckets.json (same file the Python side loads).
import { BUCKET_DEFS, formatsForBucket } from "./format-buckets";

interface QueueGroup {
  label: string;
  points: number;
  formats: readonly string[];
  rule?: "lcq_draft_2";
}

const DEFAULT_QUEUE_GROUPS: readonly QueueGroup[] = BUCKET_DEFS.map((d) => ({
  ...d,
  formats: formatsForBucket(d.label),
}));

export interface ScoringStatRow {
  format: string;
  wins: number;
  losses: number;
  trophies: number;
  events: number;
}

function groupFor(format: string): QueueGroup | undefined {
  for (const g of DEFAULT_QUEUE_GROUPS) {
    if (g.formats.includes(format)) return g;
  }
  return undefined;
}

export function computeScore(rows: ScoringStatRow[]): number {
  const grouped = new Map<string, ScoringStatRow[]>();
  for (const row of rows) {
    const g = groupFor(row.format);
    if (!g) continue;
    const list = grouped.get(g.label) ?? [];
    list.push(row);
    grouped.set(g.label, list);
  }

  let total = 0;
  for (const g of DEFAULT_QUEUE_GROUPS) {
    const rs = grouped.get(g.label);
    if (!rs || rs.length === 0) continue;

    if (g.rule === "lcq_draft_2") {
      const wins = rs.reduce((s, r) => s + r.wins, 0);
      const losses = rs.reduce((s, r) => s + r.losses, 0);
      const games = wins + losses;
      if (games === 0 || wins === 0) continue;
      total += wins * (wins / games) * g.points;
      continue;
    }

    const trophies = rs.reduce((s, r) => s + r.trophies, 0);
    const events = rs.reduce((s, r) => s + r.events, 0);
    if (trophies === 0 || events === 0) continue;
    const trophyRate = trophies / events;
    const shrinkage = trophies / (trophies + 2);
    total += trophies * g.points * trophyRate * shrinkage;
  }

  return Math.round(total * 100) / 100;
}

export function bucketScoreContribution(
  label: string,
  events: number,
  wins: number,
  losses: number,
  trophies: number,
): number {
  const g = DEFAULT_QUEUE_GROUPS.find(g => g.label === label);
  if (!g) return 0;

  if (g.rule === "lcq_draft_2") {
    const games = wins + losses;
    if (games === 0 || wins === 0) return 0;
    return Math.round(wins * (wins / games) * g.points * 100) / 100;
  }

  if (trophies === 0 || events === 0) return 0;
  const trophyRate = trophies / events;
  const shrinkage = trophies / (trophies + 2);
  return Math.round(trophies * g.points * trophyRate * shrinkage * 100) / 100;
}
