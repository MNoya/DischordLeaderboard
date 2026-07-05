import { useMemo } from "react";
import { SectionLabel } from "../SectionLabel";
import { PickGrid } from "./CommunityGrid";
import { CtaPill } from "../CtaPill";
import { DiscordIcon } from "../BrandIcons";
import { MidwayBreakdownList } from "./MidwayBreakdownList";
import { useMidwayVersusPager, MidwayVersusModal } from "./MidwayVersusCard";
import { SLOTS } from "../../data/p0p1Slots";
import {
  buildRatingsByName,
  scoreBallot,
  bestPossibleTeam,
  mostPopularTeam,
  buildMidwaySlotVersus,
  gihwrBounds,
  GIH_SAMPLE_FLOOR,
} from "../../data/p0p1Results";
import type { RatingsSnapshot, TeamPick, CardRating, GihwrBounds } from "../../data/p0p1Results";
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

function teamToEntries(picks: TeamPick[], setCode: string): PickEntry[] {
  const bySlot = new Map(picks.map((p) => [p.slot, p]));
  return SLOTS.map((slot) => {
    const pick = bySlot.get(slot.key);
    if (!pick?.cardName) return { slotKey: slot.key, label: slot.label, stats: [] };
    return {
      slotKey: slot.key,
      label: slot.label,
      stats: [{ setCode, slot: slot.key as SlotKey, cardName: pick.cardName, pickCount: 0, pickPct: 0 }],
      pctLabel: pick.gihwr > 0 ? gihwrLabel(pick.gihwr) : "—",
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
  onTileOpen,
}: {
  title: string;
  score: number;
  entries: PickEntry[];
  cardsByName: Map<string, Card>;
  onTileOpen?: (slotKey: SlotKey) => void;
}) {
  return (
    <div>
      <div className="flex items-center justify-center gap-3 mb-2">
        <SectionLabel size={22} color="white">
          {title}
        </SectionLabel>
        <span className="inline-flex items-baseline gap-[7px] rounded border border-border2 bg-surface2 px-[9px] py-1">
          <span className="font-mono tabular-nums text-[16px] font-semibold text-subtle">{score.toFixed(1)}</span>
          <span className="font-display tracking-[0.16em] text-[11px] text-muted">GIH</span>
        </span>
      </div>
      <PickGrid entries={entries} cardsByName={cardsByName} onTileOpen={onTileOpen} />
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
  const bounds = useMemo(
    () => gihwrBounds(pickStats, ratingsByName),
    [pickStats, ratingsByName],
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

  const { setCode } = ratingsSnapshot;

  const yourEntries = useMemo(
    () => (showYourPicks ? yourPicksEntries(picksBySlot, setCode, ratingsByName) : []),
    [showYourPicks, picksBySlot, setCode, ratingsByName],
  );
  const crowdEntries = useMemo(
    () => teamToEntries(crowdTeam.picks, setCode),
    [crowdTeam.picks, setCode],
  );
  const bestEntries = useMemo(
    () => teamToEntries(bestTeam.picks, setCode),
    [bestTeam.picks, setCode],
  );

  // 3-way versus pager: one entry per slot, same order as SLOTS
  const versusList = useMemo(
    () =>
      buildMidwaySlotVersus(
        SLOTS,
        picksBySlot,
        crowdTeam,
        bestTeam,
        ratingsByName,
        cardsByName,
        showYourPicks,
      ),
    [picksBySlot, crowdTeam, bestTeam, ratingsByName, cardsByName, showYourPicks],
  );
  const pager = useMidwayVersusPager(versusList);

  const onTileOpen = (slotKey: SlotKey) => {
    const idx = SLOTS.findIndex((s) => s.key === slotKey);
    if (idx !== -1) pager.open(idx);
  };

  const yourCardBySlot = useMemo(
    () => (showYourPicks ? (picksBySlot as Map<SlotKey, string>) : new Map<SlotKey, string>()),
    [showYourPicks, picksBySlot],
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
          onTileOpen={onTileOpen}
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
        onTileOpen={onTileOpen}
      />

      <ResultsRow
        title="BEST POSSIBLE"
        score={bestTeam.score}
        entries={bestEntries}
        cardsByName={cardsByName}
        onTileOpen={onTileOpen}
      />

      <MidwayVersusModal pager={pager} bounds={bounds} />

      <MidwayBreakdownList
        cards={cards}
        cardsByName={cardsByName}
        ratingsByName={ratingsByName}
        yourCardBySlot={yourCardBySlot}
        pickStats={pickStats}
        bounds={bounds}
      />
    </div>
  );
}
