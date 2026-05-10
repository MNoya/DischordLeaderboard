// Mirrors of the curated Postgres views in `frontend-spec.md`.
// Adapter (data/adapter.ts) converts snake_case rows into these camelCase types.
// Components only ever see this shape; fixtures match it directly.

export interface SetSummary {
  code: string;
  name: string;
  startDate: string; // ISO date
  endDate: string;
  isActive: boolean;
}

export interface LeaderboardRow {
  setCode: string;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  rank: number;
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

export interface PlayerFormatBreakdown {
  setCode: string;
  slug: string;
  formatLabel: string;
  events: number;
  wins: number;
  losses: number;
  trophies: number;
  scoreContribution: number;
}

export interface PlayerDraftEvent {
  slug: string;
  setCode: string;
  eventId: string;
  seventeenlandsEventId?: string | null;
  format: string;
  expansion: string;
  wins: number;
  losses: number;
  isTrophy: boolean;
  colors: string; // 17lands convention: uppercase = main, lowercase = splash
  startedAt: string;
  finishedAt: string;
}

export interface ColorsLeaderboardRow {
  setCode: string;
  colors: string; // 'WR', 'WUBR', 'MULTI', '' for colorless
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  rank: number;
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  lastCalculatedAt: string;
}

export interface ColorsSummary {
  setCode: string;
  colors: string;
  trophies: number;
  events: number;
  players: number;
}

// Recent trophy event, enriched with the player's display name. In production
// this comes from a `public_recent_trophies` view that joins draft_events
// (where is_trophy = true) with players, ordered by finished_at DESC.
export interface RecentTrophy {
  setCode: string;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  seventeenlandsEventId?: string | null;
  format: string;
  colors: string;
  wins: number;
  losses: number;
  finishedAt: string;
}

// View-shape composite used by the player profile page.
export interface PlayerProfile {
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  setCode: string;
  rank: number;
  score: number;
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  formatBreakdown: PlayerFormatBreakdown[];
}
