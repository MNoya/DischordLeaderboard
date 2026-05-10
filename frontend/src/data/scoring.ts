// JS port of bot/scoring.py — must stay in sync with the Python source.
// Used client-side to aggregate OTHER-bucket scores from raw draft events.

interface QueueGroup {
  label: string;
  points: number;
  formats: readonly string[];
  rule?: "lcq_draft_2";
}

const DEFAULT_QUEUE_GROUPS: readonly QueueGroup[] = [
  { label: "Premier", points: 10, formats: ["PremierDraft"] },
  { label: "Traditional", points: 8, formats: ["TradDraft"] },
  { label: "Sealed", points: 8, formats: ["Sealed", "TradSealed", "ArenaDirect_Sealed", "QualifierPlayInSealed"] },
  { label: "Quick", points: 4, formats: ["QuickDraft", "PickTwoDraft", "Emblem_QuickDraft"] },
  { label: "LCQ Draft 1", points: 30, formats: ["LimitedChampionshipQualifier_Draft1"] },
  { label: "LCQ Draft 2", points: 10, formats: ["LimitedChampionshipQualifier_Draft2"], rule: "lcq_draft_2" },
];

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
