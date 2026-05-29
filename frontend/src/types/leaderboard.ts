// Mirrors of the curated Postgres views in `frontend-spec.md`.
// Adapter (data/adapter.ts) converts snake_case rows into these camelCase types.
// Components only ever see this shape; fixtures match it directly.

export interface SetSummary {
  code: string;
  name: string;
  startDate: string; // ISO date
  endDate: string;
  isActive: boolean;
  custom?: boolean; // synthesized for pod-only cube formats with no row in `sets`
}

export interface PodSetCode {
  code: string;
  label: string | null; // format_label — non-null only for custom cube formats
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
  startedAt: string | null;
  finishedAt: string | null;
  // 17lands deck URL for 17L events, Draftmancer draft log for pod drafts, null if no link
  externalUrl?: string | null;
  // Pod draft event name (e.g. "Pod Draft #3"). Null for 17lands rows
  eventName?: string | null;
  // Pod draft event slug for /pods/<slug>. Null for 17lands rows
  podEventSlug?: string | null;
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

export interface PodEventSummary {
  eventId: string;
  slug: string;
  name: string;
  setCode: string;
  eventDate: string;
  eventTime: string;
  formatLabel: string | null;
  totalRounds: number;
  championPlayerSlug: string | null;
  championDisplayName: string | null;
  championAvatarUrl: string | null;
  championDeckColors: string | null;
  championRecord: string | null;
  participantCount: number;
  isFinalized: boolean;
  discordEventId: string | null;
}

export interface PodEventParticipantRow {
  eventId: string;
  displayName: string;
  seatIndex: number | null;
  placement: number | null;
  record: string | null;
  deckColors: string | null;
  draftLogUrl: string | null;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption: string | null;
  playerSlug: string | null;
  playerDisplayName: string | null;
  avatarUrl: string | null;
}

export interface PodEventMatchRow {
  eventId: string;
  eventName: string;
  round: number;
  playerAName: string;
  playerBName: string;
  winnerName: string | null;
  score: string | null;
  reportedAt: string | null;
}

export interface PodSeat extends PodEventParticipantRow {
  seatIndex: number;
  discordName: string;
}

export interface PodEventReplayRow {
  eventId: string;
  eventName: string;
  eventDate: string;
  setCode: string;
  playerId: string;
  playerSlug: string;
  playerDisplayName: string;
  gameId: string;
  link: string;
  gameTime: string;
  won: boolean;
  turns: number | null;
  onPlay: boolean | null;
  inferredRound: number | null;
}

export interface PodLeaderboardRow {
  setCode: string;
  rank: number;
  slug: string;
  displayName: string;
  avatarUrl: string | null;
  events: number;
  wins: number;
  losses: number;
  trophies: number;
  lastFinishedAt: string | null;
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
