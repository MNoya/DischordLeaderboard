import type {
  PodEventParticipantRow,
  PodEventSummary,
  PodLeaderboardRow,
} from "../../types/leaderboard";
import { podSos3Fixture, type PodParticipant } from "./pod-sos-3";

function participantToRow(p: PodParticipant): PodEventParticipantRow {
  return {
    eventId: p.eventId,
    displayName: p.displayName,
    placement: p.placement ?? null,
    record: p.record,
    deckColors: p.deckColors,
    draftLogUrl: p.draftLogUrl,
    deckScreenshotUrl: p.deckScreenshotUrl,
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
  };
}

const extraSummaries: PodEventSummary[] = [
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
  },
];

export const podEventsFixture: PodEventSummary[] = [
  summaryFromFixture(),
  ...extraSummaries,
];

export const podEventParticipantsFixture: PodEventParticipantRow[] =
  podSos3Fixture.participants.map(participantToRow);

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
