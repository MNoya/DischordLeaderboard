import { useMemo } from "react";
import { SectionLabel } from "../SectionLabel";
import { PickGrid } from "./CommunityGrid";
import { CtaPill } from "../CtaPill";
import { DiscordIcon } from "../BrandIcons";
import { SLOTS } from "../../data/p0p1Slots";
import {
  buildRatingsByName,
  scoreBallot,
  bestPossibleTeam,
  mostPopularTeam,
  GIH_SAMPLE_FLOOR,
} from "../../data/p0p1Results";
import type { RatingsSnapshot, TeamPick, CardRating } from "../../data/p0p1Results";
import type { Card, P0P1PickStat, SlotKey } from "../../types/p0p1";
import type { PickEntry } from "./CommunityGrid";

function gihwrLabel(gihwr: number): string {
  return `${(gihwr * 100).toFixed(1)}%`;
}

function formatDateEnd(iso: string): string {
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function teamToEntries(
  picks: TeamPick[],
  setCode: string,
  userPicksBySlot?: Map<string, string>,
): PickEntry[] {
  const bySlot = new Map(picks.map((p) => [p.slot, p]));
  return SLOTS.map((slot) => {
    const pick = bySlot.get(slot.key);
    if (!pick?.cardName) return { slotKey: slot.key, label: slot.label, stats: [] };
    return {
      slotKey: slot.key,
      label: slot.label,
      stats: [{ setCode, slot: slot.key as SlotKey, cardName: pick.cardName, pickCount: 0, pickPct: 0 }],
      pctLabel: pick.gihwr > 0 ? gihwrLabel(pick.gihwr) : "—",
      matchDot: userPicksBySlot ? userPicksBySlot.get(slot.key) === pick.cardName : false,
    };
  });
}

function yourPicksEntries(
  picksBySlot: Map<string, string>,
  setCode: string,
  ratingsByName: Map<string, CardRating>,
): PickEntry[] {
  return SLOTS.map((slot) => {
    const cardName = picksBySlot.get(slot.key);
    if (!cardName) return { slotKey: slot.key, label: slot.label, stats: [] };
    const rating = ratingsByName.get(cardName);
    const gihwr =
      rating && rating.gih >= GIH_SAMPLE_FLOOR && rating.gihwr !== null ? rating.gihwr : null;
    return {
      slotKey: slot.key,
      label: slot.label,
      stats: [{ setCode, slot: slot.key as SlotKey, cardName, pickCount: 0, pickPct: 0 }],
      pctLabel: gihwr !== null ? gihwrLabel(gihwr) : "—",
    };
  });
}

function ResultsRow({
  title,
  score,
  entries,
  cardsByName,
}: {
  title: string;
  score: number;
  entries: PickEntry[];
  cardsByName: Map<string, Card>;
}) {
  return (
    <div>
      <div className="flex flex-col items-center mb-2">
        <SectionLabel size={22} color="white">
          {title}
        </SectionLabel>
        <span className="font-mono tabular-nums text-[18px] leading-snug text-subtle mt-0.5">
          {score.toFixed(1)}
        </span>
      </div>
      <PickGrid entries={entries} cardsByName={cardsByName} />
    </div>
  );
}

export function MidwayResults({
  ratingsSnapshot,
  pickStats,
  cards,
  cardsByName,
  picksBySlot,
  user,
  signIn,
  hasParticipated,
}: {
  ratingsSnapshot: RatingsSnapshot;
  pickStats: P0P1PickStat[];
  cards: Card[];
  cardsByName: Map<string, Card>;
  picksBySlot: Map<string, string>;
  user: object | null;
  signIn: () => void;
  hasParticipated: boolean;
}) {
  const ratingsByName = useMemo(
    () => buildRatingsByName(ratingsSnapshot),
    [ratingsSnapshot],
  );
  const crowdTeam = useMemo(
    () => mostPopularTeam(pickStats, SLOTS, ratingsByName),
    [pickStats, ratingsByName],
  );
  const bestTeam = useMemo(
    () => bestPossibleTeam(cards, SLOTS, ratingsByName),
    [cards, ratingsByName],
  );

  const showYourPicks = Boolean(user) && hasParticipated;
  const loggedOut = !user;
  const yourScore = showYourPicks
    ? scoreBallot(picksBySlot as Map<SlotKey, string>, ratingsByName)
    : null;
  const dateCaption = ratingsSnapshot.dateRange
    ? formatDateEnd(ratingsSnapshot.dateRange.end)
    : null;

  const userPicksForDot = showYourPicks ? picksBySlot : undefined;

  const { setCode } = ratingsSnapshot;

  const yourEntries = useMemo(
    () => (showYourPicks ? yourPicksEntries(picksBySlot, setCode, ratingsByName) : []),
    [showYourPicks, picksBySlot, setCode, ratingsByName],
  );
  const crowdEntries = useMemo(
    () => teamToEntries(crowdTeam.picks, setCode, userPicksForDot),
    [crowdTeam.picks, setCode, userPicksForDot],
  );
  const bestEntries = useMemo(
    () => teamToEntries(bestTeam.picks, setCode, userPicksForDot),
    [bestTeam.picks, setCode, userPicksForDot],
  );

  return (
    <div className="flex flex-col gap-8">
      {dateCaption && (
        <p className="text-center text-dim font-mono text-[11px] tracking-widest uppercase">
          17lands data through {dateCaption} · midway snapshot
        </p>
      )}

      {showYourPicks && (
        <ResultsRow
          title="YOUR PICKS"
          score={yourScore!}
          entries={yourEntries}
          cardsByName={cardsByName}
        />
      )}

      {loggedOut && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={signIn}
            className="bg-transparent border-0 cursor-pointer p-0"
          >
            <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
              LOG IN TO VIEW YOUR PICKS
            </CtaPill>
          </button>
        </div>
      )}

      <ResultsRow
        title="CROWD TEAM"
        score={crowdTeam.score}
        entries={crowdEntries}
        cardsByName={cardsByName}
      />

      <ResultsRow
        title="BEST POSSIBLE"
        score={bestTeam.score}
        entries={bestEntries}
        cardsByName={cardsByName}
      />
    </div>
  );
}
