import { useState } from "react";
import { Link } from "react-router-dom";
import { Clock, ExternalLink } from "lucide-react";
import { TbCards } from "react-icons/tb";
import { AAvatar } from "../Brand";
import { Pips } from "../ManaPips";
import { RankBadge } from "../RankBadge";
import { Record } from "../Record";
import { cn } from "../../lib/utils";
import { useIsMobile } from "../../lib/use-is-mobile";
import { DeckScreenshotModal } from "./DeckScreenshotModal";
import type { PodMatch, PodParticipant, PodReplayRow } from "../../data/fixtures/pod-sos-3";

interface Props {
  participant: PodParticipant;
  participantsBySeatName: Map<string, PodParticipant>;
  matches: PodMatch[];
  replays: PodReplayRow[];
  onRoundHover?: (opponentSeatIndex: number | null, round: number | null, won: boolean | null) => void;
}

export function PlayerSeatPanel({
  participant,
  participantsBySeatName,
  matches,
  replays,
  onRoundHover,
}: Props) {
  const [deckView, setDeckView] = useState<PodParticipant | null>(null);
  const playerMatches = matches
    .filter((m) => m.playerA === participant.displayName || m.playerB === participant.displayName)
    .sort((a, b) => a.round - b.round);

  return (
    <div>
      <SeatHeader participant={participant} onViewDeck={() => setDeckView(participant)} />
      <div className="flex flex-col">
        {playerMatches.map((match) => {
          const opponentName = match.playerA === participant.displayName ? match.playerB : match.playerA;
          const opponent = participantsBySeatName.get(opponentName);
          return (
            <RoundRow
              key={match.round}
              match={match}
              participant={participant}
              opponentName={opponentName}
              opponent={opponent}
              replays={replays}
              onHover={onRoundHover}
              onViewDeck={(p) => setDeckView(p)}
            />
          );
        })}
      </div>
      {deckView && (
        <DeckScreenshotModal participant={deckView} onClose={() => setDeckView(null)} />
      )}
    </div>
  );
}

function SeatHeader({
  participant,
  onViewDeck,
}: {
  participant: PodParticipant;
  onViewDeck: () => void;
}) {
  const isChampion = participant.placement === 1;
  const wins = Number(participant.record.split("-")[0]);
  const losses = Number(participant.record.split("-")[1]);
  const hasDeck = participant.deckScreenshotUrl !== null;
  return (
    <header className="flex flex-col gap-4 px-4 md:px-5 xl:px-8 py-5 border-b border-border">
      <div className="flex items-center gap-4 min-w-0">
        <AAvatar
          displayName={participant.displayName}
          avatarUrl={null}
          size={60}
          green={isChampion}
        />
        <div className="min-w-0 flex-1 flex items-start justify-between gap-3">
          <div className="min-w-0 flex flex-col gap-2">
            <Link
              to={`/player/${participant.slug}`}
              target="_blank"
              rel="noreferrer noopener"
              className="font-display leading-none no-underline text-text hover:text-green transition-colors truncate"
              style={{ fontSize: 32, letterSpacing: "0.04em" }}
            >
              {participant.displayName}
            </Link>
            <div className="flex items-center gap-4 flex-wrap text-muted" style={{ fontSize: 15 }}>
              <span className="inline-flex items-center gap-2">
                <Pips colors={participant.deckColors} size={14} />
                <span className="font-display tracking-[0.18em] uppercase">
                  {isChampion ? "Champion" : `${ordinalLabel(participant.placement)} place`}
                </span>
              </span>
              <span
                className="font-display tabular-nums whitespace-nowrap"
                style={{ fontSize: 17, letterSpacing: "0.1em" }}
              >
                <Record wins={wins} losses={losses} mono separatorMargin={2} />
              </span>
            </div>
          </div>
          <RankBadge rank={participant.placement} size="md" />
        </div>
      </div>
      <div className="flex items-center gap-2">
        {hasDeck ? (
          <button
            type="button"
            onClick={onViewDeck}
            className="inline-flex items-center justify-center gap-2 bg-bg border border-border2 hover:border-green hover:text-green text-text font-display tracking-[0.14em] px-4 cursor-pointer transition-colors flex-1"
            style={{ fontSize: 14, height: 38 }}
          >
            <span>VIEW DECK</span>
            <TbCards size={16} aria-hidden="true" />
          </button>
        ) : (
          <span
            className="inline-flex items-center justify-center gap-2 bg-bg border border-border text-dim font-display tracking-[0.14em] px-4 cursor-not-allowed flex-1"
            style={{ fontSize: 14, height: 38 }}
            title="No deck screenshot available"
          >
            <span>DECK MISSING</span>
          </span>
        )}
        {participant.draftLogUrl ? (
          <a
            href={participant.draftLogUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center justify-center gap-2 bg-bg border border-border2 hover:border-green hover:text-green text-text font-display tracking-[0.14em] px-4 no-underline transition-colors flex-1"
            style={{ fontSize: 14, height: 38 }}
          >
            <span>VIEW DRAFT LOG</span>
            <ExternalLink size={15} aria-hidden="true" />
          </a>
        ) : (
          <span
            className="inline-flex items-center justify-center gap-2 bg-bg border border-border text-dim font-display tracking-[0.14em] px-4 cursor-not-allowed flex-1"
            style={{ fontSize: 14, height: 38 }}
            title="No draft log available"
          >
            <span>NO DRAFT LOG</span>
          </span>
        )}
      </div>
    </header>
  );
}

function ordinalLabel(n: number): string {
  const v = n % 100;
  const suffix = v >= 11 && v <= 13
    ? "th"
    : n % 10 === 1
      ? "st"
      : n % 10 === 2
        ? "nd"
        : n % 10 === 3
          ? "rd"
          : "th";
  return `${n}${suffix}`;
}

function RoundRow({
  match,
  participant,
  opponentName,
  opponent,
  replays,
  onHover,
  onViewDeck,
}: {
  match: PodMatch;
  participant: PodParticipant;
  opponentName: string;
  opponent: PodParticipant | undefined;
  replays: PodReplayRow[];
  onHover?: (opponentSeatIndex: number | null, round: number | null, won: boolean | null) => void;
  onViewDeck: (participant: PodParticipant) => void;
}) {
  const isMobile = useIsMobile();
  const won = match.winner === participant.displayName;
  const yourScore = won ? match.score.split("-")[0] : match.score.split("-")[1];
  const oppScore = won ? match.score.split("-")[1] : match.score.split("-")[0];

  const playerGames = replays
    .filter((r) => r.playerId === participant.playerId && r.inferredRound === match.round)
    .sort((a, b) => new Date(a.gameTime).getTime() - new Date(b.gameTime).getTime());

  const opponentGames = opponent
    ? replays
        .filter((r) => r.playerId === opponent.playerId && r.inferredRound === match.round)
        .sort((a, b) => new Date(a.gameTime).getTime() - new Date(b.gameTime).getTime())
    : [];

  const matchDurationMin = computeMatchDurationMin(playerGames, opponentGames, match.reportedAt);

  const handleEnter = () => {
    if (opponent) onHover?.(opponent.seatIndex, match.round, won);
  };
  const handleLeave = () => {
    onHover?.(null, null, null);
  };

  const opponentNameLink = opponent ? (
    isMobile ? (
      <span className="flex flex-col gap-1 min-w-0">
        <Link
          to={`/player/${opponent.slug}`}
          target="_blank"
          rel="noreferrer noopener"
          className="font-display text-text hover:text-green transition-colors no-underline truncate"
          style={{ fontSize: 21, letterSpacing: "0.03em" }}
          onClick={(e) => e.stopPropagation()}
        >
          {opponentName}
        </Link>
        <Pips colors={opponent.deckColors} size={14} />
      </span>
    ) : (
      <span className="flex items-center min-w-0 gap-2">
        <Pips colors={opponent.deckColors} size={14} />
        <Link
          to={`/player/${opponent.slug}`}
          target="_blank"
          rel="noreferrer noopener"
          className="font-display text-text hover:text-green transition-colors no-underline truncate"
          style={{ fontSize: 21, letterSpacing: "0.03em" }}
          onClick={(e) => e.stopPropagation()}
        >
          {opponentName}
        </Link>
      </span>
    )
  ) : (
    <span className="font-display text-text truncate" style={{ fontSize: 21 }}>
      {opponentName}
    </span>
  );

  const deckButton = opponent ? (
    opponent.deckScreenshotUrl ? (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onViewDeck(opponent);
        }}
        title={`View ${opponentName}'s deck`}
        className="group/deck inline-flex items-center gap-2 bg-bg border border-border hover:border-green/60 hover:bg-green/10 transition-colors px-3 cursor-pointer shrink-0"
        style={{ height: 34 }}
      >
        <span
          className="font-display tracking-[0.16em] text-text group-hover/deck:text-green transition-colors leading-none whitespace-nowrap"
          style={{ fontSize: 14 }}
        >
          VIEW DECK
        </span>
        <TbCards
          size={17}
          aria-hidden="true"
          className="text-text group-hover/deck:text-green transition-colors"
        />
      </button>
    ) : (
      <span
        className="inline-flex items-center gap-2 bg-bg border border-border text-dim leading-none cursor-not-allowed shrink-0 px-3"
        style={{ fontSize: 14, height: 34 }}
        title={`No deck screenshot available`}
      >
        <span className="font-display tracking-[0.16em] whitespace-nowrap">
          DECK MISSING
        </span>
        <TbCards size={17} aria-hidden="true" />
      </span>
    )
  ) : null;

  const durationBadge = matchDurationMin != null ? (
    <span className="inline-flex items-center gap-1.5 text-muted tabular-nums font-mono" style={{ fontSize: 13 }}>
      <Clock size={14} aria-hidden="true" />
      {`${matchDurationMin} min`}
    </span>
  ) : null;

  return (
    <section
      className="border-b border-border last:border-b-0"
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      <div
        className={cn(
          "grid items-center gap-3 px-4 md:px-5 xl:px-8 py-3",
          isMobile ? "grid-cols-[auto_1fr_auto]" : "grid-cols-[auto_auto_1fr_auto]",
        )}
      >
        <ResultBadge won={won} yourScore={yourScore} oppScore={oppScore} />
        {!isMobile && (
          <span className="text-text font-display tracking-[0.12em] ml-2" style={{ fontSize: 16 }}>
            vs.
          </span>
        )}
        <span className="flex items-center gap-2.5 min-w-0">
          {isMobile && (
            <span className="text-text font-display tracking-[0.12em] shrink-0" style={{ fontSize: 16 }}>
              vs.
            </span>
          )}
          {opponentNameLink}
          {!isMobile && deckButton}
        </span>
        {isMobile ? (
          <div className="flex flex-col items-end gap-1.5">
            {durationBadge ?? <span aria-hidden="true" />}
            {deckButton}
          </div>
        ) : (
          durationBadge ?? <span aria-hidden="true" />
        )}
      </div>

      <GamesGrid
        playerGames={playerGames}
        opponentGames={opponentGames}
        reportedAt={match.reportedAt}
      />
    </section>
  );
}

function ResultBadge({ won, yourScore, oppScore }: { won: boolean; yourScore: string; oppScore: string }) {
  const isMobile = useIsMobile();
  return (
    <span
      className={cn(
        "flex flex-col items-center justify-center font-display leading-none py-2",
        isMobile ? "px-2" : "px-3",
        won ? "bg-green/15 border border-green/55 text-green" : "bg-red/10 border border-red/45 text-red",
      )}
      style={{ minWidth: isMobile ? 52 : 72, letterSpacing: "0.08em" }}
    >
      <span style={{ fontSize: isMobile ? 16 : 20 }}>{won ? "WIN" : "LOSS"}</span>
      <span
        className="tabular-nums opacity-90 mt-1.5"
        style={{ fontSize: isMobile ? 13 : 16 }}
      >
        {yourScore}–{oppScore}
      </span>
    </span>
  );
}

function GamesGrid({
  playerGames,
  opponentGames,
  reportedAt,
}: {
  playerGames: PodReplayRow[];
  opponentGames: PodReplayRow[];
  reportedAt: string;
}) {
  const isMobile = useIsMobile();
  if (playerGames.length === 0 && opponentGames.length === 0) {
    return (
      <div className="px-4 md:px-5 xl:px-8 py-4 text-muted text-[13px] font-body">
        No replays were captured for either seat this round.
      </div>
    );
  }
  const gameCount = Math.max(playerGames.length, opponentGames.length);
  const playerDurations = computeGameDurationsMin(playerGames, reportedAt);

  return (
    <div className="px-4 md:px-5 xl:px-8 pb-4 pt-2 flex flex-col gap-2">
      {Array.from({ length: gameCount }, (_, i) => {
        const pg = playerGames[i] ?? null;
        const og = pg ? findOpponentPov(pg, opponentGames) : (opponentGames[i] ?? null);
        const hideOpponent = isMobile && !og;
        return (
          <div
            key={i}
            className={cn(
              "grid items-stretch",
              hideOpponent ? "grid-cols-1" : "grid-cols-[1fr_auto] gap-2",
            )}
          >
            <PlayerReplayCell row={pg} durationMin={pg ? playerDurations[i] : null} />
            {!hideOpponent && <OpponentReplayCell row={og} />}
          </div>
        );
      })}
    </div>
  );
}

function PlayerReplayCell({
  row,
  durationMin,
}: {
  row: PodReplayRow | null;
  durationMin: number | null | undefined;
}) {
  const isMobile = useIsMobile();
  if (!row) {
    return (
      <div
        className="flex items-center bg-bg border border-border text-dim cursor-default px-3"
        style={{ height: 38 }}
        title="No replay was captured for this game"
      >
        <span
          className="font-display tracking-[0.16em] leading-none whitespace-nowrap"
          style={{ fontSize: 12 }}
        >
          {isMobile ? "NO REPLAY" : "NO REPLAY CAPTURED"}
        </span>
      </div>
    );
  }
  return (
    <a
      href={row.link}
      target="_blank"
      rel="noreferrer noopener"
      onClick={(e) => e.stopPropagation()}
      style={{ height: 38 }}
      className={cn(
        "group grid items-center gap-3 bg-bg border border-border hover:border-green/60 hover:bg-green/10 transition-colors px-3 no-underline",
        isMobile ? "grid-cols-[auto_1fr_auto_auto]" : "grid-cols-[auto_1fr_auto_auto_auto]",
      )}
    >
      <span
        className={cn("font-display tabular-nums leading-none", row.won ? "text-green" : "text-red")}
        style={{ fontSize: 20, letterSpacing: "0.12em" }}
      >
        {row.won ? "W" : "L"}
      </span>
      <span className="text-subtle font-mono tabular-nums truncate leading-none" style={{ fontSize: 13 }}>
        {row.turns != null ? `${row.turns} turns` : "—"}
        {row.onPlay != null && (
          <span className="text-dim ml-2">{row.onPlay ? "Play" : "Draw"}</span>
        )}
      </span>
      {!isMobile && (
        <span className="text-dim font-mono tabular-nums leading-none" style={{ fontSize: 12 }}>
          {durationMin != null ? `${durationMin} min` : ""}
        </span>
      )}
      <span
        className="font-display tracking-[0.16em] text-text group-hover:text-green transition-colors leading-none whitespace-nowrap"
        style={{ fontSize: 12 }}
      >
        {isMobile ? "REPLAY" : "VIEW REPLAY"}
      </span>
      <ExternalLink
        size={13}
        aria-hidden="true"
        className="text-text group-hover:text-green transition-colors"
      />
    </a>
  );
}

function OpponentReplayCell({ row }: { row: PodReplayRow | null }) {
  const isMobile = useIsMobile();
  if (!row) {
    if (isMobile) return null;
    return (
      <div
        className="inline-flex items-center bg-bg border border-border text-dim cursor-default px-3"
        style={{ height: 38 }}
        title="No opponent replay was captured for this game"
      >
        <span
          className="font-display tracking-[0.16em] leading-none whitespace-nowrap"
          style={{ fontSize: 12 }}
        >
          NO REPLAY CAPTURED
        </span>
      </div>
    );
  }
  return (
    <a
      href={row.link}
      target="_blank"
      rel="noreferrer noopener"
      onClick={(e) => e.stopPropagation()}
      style={{ height: 38 }}
      className="group inline-flex items-center gap-1.5 bg-bg border border-border hover:border-green/60 hover:bg-green/10 transition-colors px-3 no-underline"
    >
      <span
        className="font-display tracking-[0.16em] text-text group-hover:text-green transition-colors leading-none whitespace-nowrap"
        style={{ fontSize: 12 }}
      >
        {isMobile ? "OPP REPLAY" : "VIEW OPPONENT'S REPLAY"}
      </span>
      <ExternalLink
        size={13}
        aria-hidden="true"
        className="text-text group-hover:text-green transition-colors"
      />
    </a>
  );
}

function findOpponentPov(playerGame: PodReplayRow, opponentGames: PodReplayRow[]): PodReplayRow | null {
  const playerTime = new Date(playerGame.gameTime).getTime();
  for (const r of opponentGames) {
    if (r.turns !== playerGame.turns) continue;
    if (r.won === playerGame.won) continue;
    const rTime = new Date(r.gameTime).getTime();
    if (Math.abs(rTime - playerTime) <= 2 * 60_000) return r;
  }
  return null;
}

function computeGameDurationsMin(games: PodReplayRow[], reportedAt: string): (number | null)[] {
  if (games.length === 0) return [];
  const reported = new Date(reportedAt).getTime();
  return games.map((g, i) => {
    const thisTime = new Date(g.gameTime).getTime();
    const nextTime = i + 1 < games.length ? new Date(games[i + 1].gameTime).getTime() : reported;
    const min = Math.max(0, Math.round((nextTime - thisTime) / 60_000));
    return min > 0 ? min : null;
  });
}

function computeMatchDurationMin(
  playerGames: PodReplayRow[],
  opponentGames: PodReplayRow[],
  reportedAt: string,
): number | null {
  const allTimes = [
    ...playerGames.map((g) => new Date(g.gameTime).getTime()),
    ...opponentGames.map((g) => new Date(g.gameTime).getTime()),
  ];
  if (allTimes.length === 0) return null;
  const firstStart = Math.min(...allTimes);
  const reported = new Date(reportedAt).getTime();
  const min = Math.max(0, Math.round((reported - firstStart) / 60_000));
  return min > 0 ? min : null;
}
