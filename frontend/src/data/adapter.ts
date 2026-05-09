// Adapter layer (spec §4).
//
// In production this converts snake_case rows from Supabase into the camelCase
// UI types. Today everything is fixture-mocked in `mockApi.ts` already, so this
// is a placeholder ready for real-backend wiring.
//
// Usage when the bot lands:
//
//   const { data, error } = await supabase.from("public_leaderboard")
//     .select("*").eq("set_code", setCode);
//   return data.map(adaptLeaderboardRow);

import type {
  ArchetypeLeaderboardRow,
  LeaderboardRow,
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  SetSummary,
} from "../types/leaderboard";

type SnakeRow = Record<string, unknown>;

const camelCaseKey = (key: string): string =>
  key.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase());

const camelify = <T,>(row: SnakeRow): T => {
  const out: SnakeRow = {};
  for (const k in row) out[camelCaseKey(k)] = row[k];
  return out as T;
};

export const adaptSet = (row: SnakeRow): SetSummary => camelify(row);
export const adaptLeaderboardRow = (row: SnakeRow): LeaderboardRow =>
  camelify(row);
export const adaptArchetypeRow = (row: SnakeRow): ArchetypeLeaderboardRow =>
  camelify(row);
export const adaptFormatBreakdown = (row: SnakeRow): PlayerFormatBreakdown =>
  camelify(row);
export const adaptDraftEvent = (row: SnakeRow): PlayerDraftEvent =>
  camelify(row);
