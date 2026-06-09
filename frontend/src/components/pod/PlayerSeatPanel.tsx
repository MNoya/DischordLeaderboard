import { Link } from "react-router-dom";
import { AAvatar } from "../Brand";
import {
  Clock,
  ExternalLink,
  LuScrollText,
  TbCards,
} from "../Icons";
import { Pips } from "../ManaPips";
import { Record } from "../Record";
import { cn } from "../../lib/utils";
import { useIsMobile } from "../../lib/use-is-mobile";
import { playerPath, podSeatName, stripDiscriminator } from "../../data/utils";
import type { PodEventMatchRow, PodEventReplayRow, PodSeat } from "../../types/leaderboard";

const SKIPPED_SENTINEL = "(skipped)";

export type RoundOutcome = "win" | "loss" | "skip" | "pending";

interface Props {
  participant: PodSeat;
  participantsBySeatName: Map<string, PodSeat>;
  matches: PodEventMatchRow[];
  replays: PodEventReplayRow[];
  setCode: string;
  linkableSlugs: Set<string>;
  onRoundHover?: (opponentSeatIndex: number | null, round: number | null, outcome: RoundOutcome | null) => void;
  onShowDeck: (p: PodSeat) => void;
  isMock?: boolean;
}

export function PlayerSeatPanel({
  participant,
  participantsBySeatName,
  matches,
  replays,
  setCode,
  linkableSlugs,
  onRoundHover,
  onShowDeck,
  isMock = false,
}: Props) {
  const seatName = podSeatName(participant);
  const playerMatches = matches
    .filter((m) => m.playerAName === seatName || m.playerBName === seatName)
    .sort((a, b) => a.round - b.round);

  const profileHref = (slug: string | null | undefined): string | null =>
    slug && linkableSlugs.has(slug) ? playerPath(slug, setCode) : null;

  return (
    <div>
      <SeatHeader
        participant={participant}
        profileHref={profileHref(participant.playerSlug)}
        onViewDeck={() => onShowDeck(participant)}
        isMock={isMock}
      />
      <div className="flex flex-col">
        {isMock ? (
          participant.deckScreenshotUrl ? (
            <>
              <button
                type="button"
                onClick={() => onShowDeck(participant)}
                className="block w-full p-0 m-0 border-0 bg-transparent cursor-zoom-in"
                aria-label={`${participant.discordName}'s deck — click to enlarge`}
              >
                <img
                  src={participant.deckScreenshotUrl}
                  alt={`${participant.discordName}'s deck`}
                  className="block w-full h-auto"
                />
              </button>
              {participant.deckScreenshotCaption && (
                <div className="px-4 md:px-5 xl:px-8 py-3 border-t border-border text-muted font-body text-[13px]">
                  {participant.deckScreenshotCaption}
                </div>
              )}
            </>
          ) : (
            <div className="px-4 md:px-5 xl:px-8 py-10 text-muted font-body text-[13px]">
              No deck screenshot posted yet.
            </div>
          )
        ) : (
          playerMatches.map((match) => {
            const opponentName =
              match.playerAName === seatName ? match.playerBName : match.playerAName;
            const opponent = participantsBySeatName.get(opponentName);
            return (
              <RoundRow
                key={match.round}
                match={match}
                participant={participant}
                opponentName={opponentName}
                opponent={opponent}
                opponentHref={profileHref(opponent?.playerSlug)}
                replays={replays}
                onHover={onRoundHover}
                onViewDeck={onShowDeck}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

function SeatHeader({
  participant,
  profileHref,
  onViewDeck,
  isMock = false,
}: {
  participant: PodSeat;
  profileHref: string | null;
  onViewDeck: () => void;
  isMock?: boolean;
}) {
  const isMobile = useIsMobile();
  const isChampion = participant.placement === 1;
  const hasRecord = participant.record != null;
  const wins = Number((participant.record ?? "").split("-")[0] || 0);
  const losses = Number((participant.record ?? "").split("-")[1] || 0);
  const hasDeck = participant.deckScreenshotUrl !== null;

  const nameLink = profileHref ? (
    <Link
      to={profileHref}
      target="_blank"
      rel="noreferrer noopener"
      className="self-start max-w-full no-underline font-display leading-none truncate text-text hover:text-green transition-colors"
      style={{ fontSize: 32, letterSpacing: "0.04em" }}
    >
      {participant.discordName}
    </Link>
  ) : (
    <span
      className="self-start max-w-full font-display leading-none truncate text-text"
      style={{ fontSize: 32, letterSpacing: "0.04em" }}
    >
      {participant.discordName}
    </span>
  );

  const placementLabel = isChampion
    ? "Champion"
    : participant.placement != null
      ? `${ordinalLabel(participant.placement)} place`
      : null;
  const metaRow = (
    <div className="flex items-baseline gap-2.5 lg:gap-4 flex-wrap text-muted" style={{ fontSize: 16 }}>
      {(participant.deckColors || hasRecord) && (
        <span className="inline-flex items-center gap-2 self-center">
          {participant.deckColors && <Pips colors={participant.deckColors} size={16} />}
          {hasRecord && (
            <span
              className="font-display tabular-nums whitespace-nowrap text-text"
              style={{ letterSpacing: "0.08em" }}
            >
              <Record wins={wins} losses={losses} mono separatorMargin={3} />
            </span>
          )}
        </span>
      )}
      {placementLabel && (
        <span
          className={cn(
            "font-display tracking-[0.16em] uppercase whitespace-nowrap",
            isChampion ? "text-green" : "text-muted",
          )}
        >
          {placementLabel}
        </span>
      )}
    </div>
  );

  if (isMobile) {
    return (
      <header className="flex flex-col gap-4 px-4 md:px-5 xl:px-8 py-7 border-b border-border">
        <div className="flex items-center gap-4 min-w-0">
          <AAvatar displayName={participant.discordName} avatarUrl={participant.avatarUrl} size={60} green={isChampion} />
          <div className="min-w-0 flex-1 flex items-start justify-between gap-3">
            <div className="min-w-0 flex flex-col gap-2">
              {nameLink}
              {metaRow}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {!isMock && (hasDeck ? (
            <button
              type="button"
              onClick={onViewDeck}
              className="inline-flex items-center justify-center gap-2 bg-bg border border-border hover:border-green/60 hover:bg-green/10 hover:text-green text-text font-display tracking-[0.14em] px-4 cursor-pointer transition-colors flex-1"
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
              <TbCards size={16} aria-hidden="true" />
            </span>
          ))}
          {participant.draftLogUrl ? (
            <a
              href={participant.draftLogUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center justify-center gap-2 bg-bg border border-border hover:border-green/60 hover:bg-green/10 hover:text-green text-text font-display tracking-[0.14em] px-4 no-underline transition-colors flex-1"
              style={{ fontSize: 14, height: 38 }}
            >
              <span>VIEW DRAFT LOG</span>
              <LuScrollText size={15} aria-hidden="true" />
            </a>
          ) : (
            <span
              className="inline-flex items-center justify-center gap-2 bg-bg border border-border text-dim font-display tracking-[0.14em] px-4 cursor-not-allowed flex-1"
              style={{ fontSize: 14, height: 38 }}
              title="No draft log available"
            >
              <span>NO DRAFT LOG</span>
              <LuScrollText size={15} aria-hidden="true" />
            </span>
          )}
        </div>
      </header>
    );
  }

  return (
    <header className="flex items-center gap-4 px-4 md:px-5 xl:px-8 py-7 border-b border-border">
      <AAvatar displayName={participant.discordName} avatarUrl={participant.avatarUrl} size={60} green={isChampion} />
      <div className="min-w-0 flex-1 flex flex-col gap-2">
        {nameLink}
        {metaRow}
      </div>
      <div className="flex flex-col gap-2 shrink-0 min-w-[200px]">
        {!isMock && (hasDeck ? (
          <button
            type="button"
            onClick={onViewDeck}
            className="inline-flex items-center justify-end gap-5 bg-bg border border-border hover:border-green/60 hover:bg-green/10 hover:text-green text-text font-display tracking-[0.12em] px-5 cursor-pointer transition-colors leading-none"
            style={{ fontSize: 17, height: 44, paddingTop: 2 }}
          >
            <span>VIEW DECK</span>
            <TbCards size={20} aria-hidden="true" />
          </button>
        ) : (
          <span
            className="inline-flex items-center justify-end gap-5 bg-bg border border-border text-dim font-display tracking-[0.12em] px-5 cursor-not-allowed leading-none"
            style={{ fontSize: 17, height: 44, paddingTop: 2 }}
            title="No deck screenshot available"
          >
            <span>DECK MISSING</span>
            <TbCards size={20} aria-hidden="true" />
          </span>
        ))}
        {participant.draftLogUrl ? (
          <a
            href={participant.draftLogUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center justify-end gap-5 bg-bg border border-border hover:border-green/60 hover:bg-green/10 hover:text-green text-text font-display tracking-[0.12em] px-5 no-underline transition-colors leading-none"
            style={{ fontSize: 17, height: 44, paddingTop: 2 }}
          >
            <span>VIEW DRAFT LOG</span>
            <LuScrollText size={20} aria-hidden="true" />
          </a>
        ) : (
          <span
            className="inline-flex items-center justify-end gap-5 bg-bg border border-border text-dim font-display tracking-[0.12em] px-5 cursor-not-allowed leading-none"
            style={{ fontSize: 17, height: 44, paddingTop: 2 }}
            title="No draft log available"
          >
            <span>NO DRAFT LOG</span>
            <LuScrollText size={20} aria-hidden="true" />
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
  opponentHref,
  replays,
  onHover,
  onViewDeck,
}: {
  match: PodEventMatchRow;
  participant: PodSeat;
  opponentName: string;
  opponent: PodSeat | undefined;
  opponentHref: string | null;
  replays: PodEventReplayRow[];
  onHover?: (opponentSeatIndex: number | null, round: number | null, outcome: RoundOutcome | null) => void;
  onViewDeck: (participant: PodSeat) => void;
}) {
  const isMobile = useIsMobile();
  const isSkipped = match.winnerName === SKIPPED_SENTINEL;
  const isPending = !isSkipped && match.winnerName == null;
  const won = !isSkipped && !isPending && match.winnerName === podSeatName(participant);
  const outcome: RoundOutcome = isSkipped ? "skip" : isPending ? "pending" : won ? "win" : "loss";
  const score = match.score ?? null;
  const yourScore = score ? (won ? score.split("-")[0] : score.split("-")[1]) : null;
  const oppScore = score ? (won ? score.split("-")[1] : score.split("-")[0]) : null;

  const participantSlug = participant.playerSlug;
  const opponentSlug = opponent?.playerSlug ?? null;

  const playerGames = participantSlug && !isSkipped
    ? replays
        .filter((r) => r.playerSlug === participantSlug && r.inferredRound === match.round)
        .sort((a, b) => new Date(a.gameTime).getTime() - new Date(b.gameTime).getTime())
    : [];

  const opponentGames = opponentSlug && !isSkipped
    ? replays
        .filter((r) => r.playerSlug === opponentSlug && r.inferredRound === match.round)
        .sort((a, b) => new Date(a.gameTime).getTime() - new Date(b.gameTime).getTime())
    : [];

  const matchDurationMin = isSkipped
    ? null
    : computeMatchDurationMin(playerGames, opponentGames, match.reportedAt);
  const opponentDisplay = opponent?.discordName ?? stripDiscriminator(opponentName);

  const handleEnter = () => {
    if (opponent) onHover?.(opponent.seatIndex, match.round, outcome);
  };
  const handleLeave = () => {
    onHover?.(null, null, null);
  };

  const opponentNameNode = opponent && opponentHref ? (
    <Link
      to={opponentHref}
      target="_blank"
      rel="noreferrer noopener"
      className="font-display text-text hover:text-green transition-colors no-underline truncate"
      style={{ fontSize: 21, letterSpacing: "0.03em" }}
      onClick={(e) => e.stopPropagation()}
    >
      {opponentDisplay}
    </Link>
  ) : (
    <span
      className="font-display text-text truncate"
      style={{ fontSize: 21, letterSpacing: "0.03em" }}
    >
      {opponentDisplay}
    </span>
  );
  const opponentNameLink = opponent ? (
    isMobile ? (
      <span className="flex flex-col gap-1 min-w-0">
        {opponentNameNode}
        {opponent.deckColors && <Pips colors={opponent.deckColors} size={14} />}
      </span>
    ) : (
      <span className="flex items-center min-w-0 gap-2">
        {opponent.deckColors && <Pips colors={opponent.deckColors} size={14} />}
        {opponentNameNode}
      </span>
    )
  ) : (
    <span className="font-display text-text truncate" style={{ fontSize: 21 }}>
      {opponentDisplay}
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
        title={`View ${opponentDisplay}'s deck`}
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
        <ResultBadge outcome={outcome} yourScore={yourScore} oppScore={oppScore} />
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

      {!isSkipped && (
        <GamesGrid
          playerGames={playerGames}
          opponentGames={opponentGames}
        />
      )}
    </section>
  );
}

function ResultBadge({
  outcome,
  yourScore,
  oppScore,
}: {
  outcome: RoundOutcome;
  yourScore: string | null;
  oppScore: string | null;
}) {
  const isMobile = useIsMobile();
  if (outcome === "skip" || outcome === "pending") {
    return (
      <span
        className={cn(
          "flex items-center justify-center font-display leading-none",
          isMobile ? "px-2" : "px-3",
          "bg-surface2/40 border border-border text-muted",
        )}
        style={{
          minWidth: isMobile ? 52 : 72,
          height: isMobile ? 42 : 56,
          letterSpacing: "0.08em",
        }}
      >
        <span style={{ fontSize: isMobile ? 14 : 18 }}>{outcome === "skip" ? "DROP" : "TBD"}</span>
      </span>
    );
  }
  const won = outcome === "win";
  const hasScore = yourScore != null && oppScore != null;
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
      {hasScore && (
        <span
          className="tabular-nums opacity-90 mt-1.5"
          style={{ fontSize: isMobile ? 13 : 16 }}
        >
          {yourScore}–{oppScore}
        </span>
      )}
    </span>
  );
}

function GamesGrid({
  playerGames,
  opponentGames,
}: {
  playerGames: PodEventReplayRow[];
  opponentGames: PodEventReplayRow[];
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
  const playerDurations = computeGameDurationsMin(playerGames);

  return (
    <div className="px-4 md:px-5 xl:px-8 pb-4 flex flex-col gap-2">
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
  row: PodEventReplayRow | null;
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
          style={{ fontSize: 14 }}
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
        style={{ fontSize: 14 }}
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

function OpponentReplayCell({ row }: { row: PodEventReplayRow | null }) {
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
          style={{ fontSize: 14 }}
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
        style={{ fontSize: 14 }}
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

function findOpponentPov(playerGame: PodEventReplayRow, opponentGames: PodEventReplayRow[]): PodEventReplayRow | null {
  const playerTime = new Date(playerGame.gameTime).getTime();
  for (const r of opponentGames) {
    if (r.turns !== playerGame.turns) continue;
    if (r.won === playerGame.won) continue;
    const rTime = new Date(r.gameTime).getTime();
    if (Math.abs(rTime - playerTime) <= 2 * 60_000) return r;
  }
  return null;
}

function computeGameDurationsMin(games: PodEventReplayRow[]): (number | null)[] {
  if (games.length === 0) return [];
  return games.map((g, i) => {
    if (i === 0) return null;
    const prevTime = new Date(games[i - 1].gameTime).getTime();
    const thisTime = new Date(g.gameTime).getTime();
    const min = Math.max(0, Math.round((thisTime - prevTime) / 60_000));
    return min > 0 ? min : null;
  });
}

function computeMatchDurationMin(
  playerGames: PodEventReplayRow[],
  opponentGames: PodEventReplayRow[],
  reportedAt: string | null,
): number | null {
  if (!reportedAt) return null;
  const allTimes = [
    ...playerGames.map((g) => new Date(g.gameTime).getTime()),
    ...opponentGames.map((g) => new Date(g.gameTime).getTime()),
  ].sort((a, b) => a - b);
  if (allTimes.length === 0) return null;
  const firstEnd = allTimes[0];
  const reported = new Date(reportedAt).getTime();
  const tailSpanMin = (reported - firstEnd) / 60_000;

  const gameCount = Math.max(playerGames.length, opponentGames.length);
  const game1EstimateMin = gameCount >= 2 ? tailSpanMin / Math.max(1, gameCount - 1) : 0;
  const totalMin = Math.max(0, Math.round(tailSpanMin + game1EstimateMin));
  return totalMin > 0 ? totalMin : null;
}
