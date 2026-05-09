import type { SetSummary } from "../../types/leaderboard";

// Snapshot from production sets table on 2026-05-08.
// SOS is the only set with player data so far; the others are scheduled placeholders.
export const setsFixture: SetSummary[] = [
  { code: "SOS", name: "Secrets of Strixhaven",      startDate: "2026-04-21", endDate: "2026-06-22", isActive: true  },
  { code: "ECL", name: "Lorwyn Eclipsed",            startDate: "2026-01-20", endDate: "2026-04-20", isActive: false },
  { code: "TLA", name: "Avatar: The Last Airbender", startDate: "2025-11-18", endDate: "2026-01-19", isActive: false },
  { code: "FIN", name: "Final Fantasy",              startDate: "2025-06-10", endDate: "2025-11-17", isActive: false },
];
