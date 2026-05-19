import type {
  PodEventMatchRow,
  PodEventParticipantRow,
  PodEventReplayRow,
  PodEventSummary,
  PodLeaderboardRow,
} from "../../types/leaderboard";
import { podSos3Fixture, type PodParticipant } from "./pod-sos-3";

function participantToRow(p: PodParticipant): PodEventParticipantRow {
  return {
    eventId: p.eventId,
    displayName: p.displayName,
    seatIndex: p.seatIndex,
    placement: p.placement ?? null,
    record: p.record,
    deckColors: p.deckColors,
    draftLogUrl: p.draftLogUrl,
    deckScreenshotUrl: p.deckScreenshotUrl,
    deckScreenshotCaption: p.deckScreenshotCaption,
    playerSlug: p.slug,
    playerDisplayName: p.displayName,
    avatarUrl: null,
  };
}

function summaryFromFixture(): PodEventSummary {
  const champion = podSos3Fixture.participants.find((p) => p.placement === 1);
  return {
    eventId: podSos3Fixture.id,
    slug: podSos3Fixture.slug,
    name: podSos3Fixture.name,
    setCode: podSos3Fixture.setCode,
    eventDate: podSos3Fixture.date,
    eventTime: `${podSos3Fixture.date}T20:00:00Z`,
    formatLabel: podSos3Fixture.formatLabel,
    totalRounds: podSos3Fixture.totalRounds,
    championPlayerSlug: champion?.slug ?? null,
    championDisplayName: champion?.displayName ?? null,
    championAvatarUrl: null,
    championDeckColors: champion?.deckColors ?? null,
    championRecord: champion?.record ?? null,
    participantCount: podSos3Fixture.participants.length,
    isFinalized: podSos3Fixture.participants.every((p) => p.placement != null),
    discordEventId: null,
  };
}

const extraSummaries: PodEventSummary[] = [
  {
    eventId: "mock-sos-4",
    slug: "sos-pod-draft-4",
    name: "SOS Pod Draft #4",
    setCode: "SOS",
    eventDate: "2026-05-20",
    eventTime: "2026-05-20T20:00:00Z",
    formatLabel: "Pod Draft · Swiss · 3 Rounds",
    totalRounds: 3,
    championPlayerSlug: null,
    championDisplayName: null,
    championAvatarUrl: null,
    championDeckColors: null,
    championRecord: null,
    participantCount: 0,
    isFinalized: false,
    discordEventId: "1505785425049030818",
  },
  {
    eventId: "mock-sos-2",
    slug: "sos-pod-draft-2",
    name: "SOS Pod Draft #2",
    setCode: "SOS",
    eventDate: "2026-05-07",
    eventTime: "2026-05-07T20:00:00Z",
    formatLabel: "Pod Draft · Swiss · 3 Rounds",
    totalRounds: 3,
    championPlayerSlug: "elfandor",
    championDisplayName: "Elfandor",
    championAvatarUrl: null,
    championDeckColors: "WR",
    championRecord: "3-0",
    participantCount: 8,
    isFinalized: true,
    discordEventId: null,
  },
  {
    eventId: "mock-sos-1",
    slug: "sos-pod-draft-1",
    name: "SOS Pod Draft #1",
    setCode: "SOS",
    eventDate: "2026-04-30",
    eventTime: "2026-04-30T20:00:00Z",
    formatLabel: "Pod Draft · Swiss · 3 Rounds",
    totalRounds: 3,
    championPlayerSlug: "noya",
    championDisplayName: "Noya",
    championAvatarUrl: null,
    championDeckColors: "WU",
    championRecord: "3-0",
    participantCount: 8,
    isFinalized: true,
    discordEventId: null,
  },
];

export const podEventsFixture: PodEventSummary[] = [
  summaryFromFixture(),
  ...extraSummaries,
];

export const podEventParticipantsFixture: PodEventParticipantRow[] =
  podSos3Fixture.participants.map(participantToRow);

export const podEventMatchesFixture: PodEventMatchRow[] = podSos3Fixture.matches.map((m) => ({
  eventId: m.eventId,
  eventName: podSos3Fixture.name,
  round: m.round,
  playerAName: m.playerA,
  playerBName: m.playerB,
  winnerName: m.winner,
  score: m.score,
  reportedAt: m.reportedAt,
}));

export const podEventReplaysFixture: PodEventReplayRow[] = podSos3Fixture.replays.map((r) => ({
  eventId: r.eventId,
  eventName: r.eventName,
  eventDate: r.eventDate,
  setCode: r.setCode,
  playerId: r.playerId,
  playerSlug: r.playerSlug,
  playerDisplayName: r.playerDisplayName,
  gameId: r.gameId,
  link: r.link,
  gameTime: r.gameTime,
  won: r.won,
  turns: r.turns,
  onPlay: r.onPlay,
  inferredRound: r.inferredRound,
}));

export const podLeaderboardFixtureRaw: Omit<PodLeaderboardRow, "rank">[] =
  podSos3Fixture.participants.map((p) => {
    const wins = Number(p.record.split("-")[0] || 0);
    const losses = Number(p.record.split("-")[1] || 0);
    return {
      setCode: podSos3Fixture.setCode,
      slug: p.slug,
      displayName: p.displayName,
      avatarUrl: null,
      events: 1,
      wins,
      losses,
      trophies: p.placement === 1 ? 1 : 0,
      lastFinishedAt: `${podSos3Fixture.date}T22:00:00Z`,
    };
  });

export const podSetCodesFixture = ["SOS"];
