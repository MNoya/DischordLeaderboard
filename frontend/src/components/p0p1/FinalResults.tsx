import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { SectionLabel } from "../SectionLabel";
import { PickGrid } from "./CommunityGrid";
import { CtaPill } from "../CtaPill";
import { DiscordIcon } from "../BrandIcons";
import { MidwayBreakdownList } from "./MidwayBreakdownList";
import { useMidwayVersusPager, MidwayVersusModal } from "./MidwayVersusCard";
import { breakdownStripAccent, SLOT_ACCENT } from "./slotVisuals";
import { CHAMFER } from "./P0P1BallotScorecard";
import { SLOTS } from "../../data/p0p1Slots";
import {
  buildRatingsByName,
  scoreBallot,
  bestPossibleTeam,
  mostPopularTeam,
  buildMidwaySlotVersus,
  gihwrBounds,
  groupBallotRows,
  rankBallots,
  slotRankGaps,
  GIH_SAMPLE_FLOOR,
} from "../../data/p0p1Results";
import type {
  RatingsSnapshot,
  TeamPick,
  CardRating,
  RankedBallot,
  SlotRankGap,
} from "../../data/p0p1Results";
import type { Card, P0P1BallotRow, P0P1PickStat, SlotKey } from "../../types/p0p1";
import type { PickEntry } from "./CommunityGrid";

const HIGHLIGHTS_COUNT = 5;

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

function ballotToEntries(ballot: RankedBallot, setCode: string, ratingsByName: Map<string, CardRating>): PickEntry[] {
  return SLOTS.map((slot) => {
    const cardName = ballot.picks.get(slot.key);
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

function findUserBallot(
  rankedBallots: RankedBallot[],
  picksBySlot: Map<string, string>,
): RankedBallot | null {
  if (picksBySlot.size === 0) return null;
  for (const ballot of rankedBallots) {
    if (ballot.picks.size !== picksBySlot.size) continue;
    let match = true;
    for (const [slot, cardName] of picksBySlot) {
      if (ballot.picks.get(slot as SlotKey) !== cardName) { match = false; break; }
    }
    if (match) return ballot;
  }
  return null;
}

// ── Per-slot contribution bar ─────────────────────────────────────────────────

interface SlotContrib {
  slotKey: SlotKey;
  label: string;
  cardName: string | null;
  card: Card | undefined;
  gihwr: number | null;
  points: number; // gihwr * 100, same units as ballot.score
}

function ballotContributions(
  ballot: RankedBallot,
  ratingsByName: Map<string, CardRating>,
  cardsByName: Map<string, Card>,
): SlotContrib[] {
  return SLOTS.map((slot) => {
    const cardName = ballot.picks.get(slot.key) ?? null;
    const card = cardName ? cardsByName.get(cardName) : undefined;
    const rating = cardName ? ratingsByName.get(cardName) : undefined;
    const gihwr =
      rating && rating.gih >= GIH_SAMPLE_FLOOR && rating.gihwr !== null
        ? rating.gihwr
        : null;
    return {
      slotKey: slot.key,
      label: slot.label,
      cardName,
      card,
      gihwr,
      points: gihwr !== null ? gihwr * 100 : 0,
    };
  });
}

function SegTooltipContent({ seg }: { seg: SlotContrib }) {
  return (
    <div className="bg-surface2 border border-border2 rounded-sm shadow-xl overflow-hidden w-[160px]">
      {seg.card ? (
        <img src={seg.card.imageNormal} alt={seg.card.name} className="w-full block" />
      ) : (
        <div className="px-2 py-1.5">
          <div className="font-display tracking-[0.1em] text-[10px] text-muted uppercase leading-none mb-0.5">
            {seg.label}
          </div>
          <div className="text-[12px] text-subtle">{seg.cardName ?? "—"}</div>
        </div>
      )}
      {seg.gihwr !== null && (
        <div className="px-2 py-1 font-mono tabular-nums text-[11px] font-semibold text-white border-t border-border2">
          {(seg.gihwr * 100).toFixed(1)}%
          <span className="ml-1.5 font-normal text-muted text-[10px]">{seg.label}</span>
        </div>
      )}
    </div>
  );
}

function ContributionBar({
  ballot,
  maxScore,
  ratingsByName,
  cardsByName,
}: {
  ballot: RankedBallot;
  maxScore: number;
  ratingsByName: Map<string, CardRating>;
  cardsByName: Map<string, Card>;
}) {
  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  const contribs = useMemo(
    () => ballotContributions(ballot, ratingsByName, cardsByName),
    [ballot, ratingsByName, cardsByName],
  );
  const activeContribs = contribs.filter((c) => c.points > 0);
  const fillPct = maxScore > 0 ? (ballot.score / maxScore) * 100 : 0;

  return (
    // self-stretch + negative vertical margins cancel the button's py-2.5/py-3 padding,
    // so the bar bleeds to the full row height while hover events still reach Layer 2.
    <div className="hidden lg:block flex-1 self-stretch -my-2.5 lg:-my-3 relative min-w-0" onClick={(e) => e.stopPropagation()}>
      {/* Layer 1: visual segments — overflow:hidden clips art to fill width */}
      <div
        className="absolute top-0 left-0 h-full flex gap-px overflow-hidden"
        style={{ width: `${fillPct}%` }}
      >
        {activeContribs.map(({ slotKey, card, gihwr, points }) => (
          <div
            key={slotKey}
            className="relative h-full overflow-hidden"
            style={{ flexGrow: points, flexBasis: 0 }}
          >
            <div
              className="absolute top-0 left-0 right-0 h-[2px] z-10 pointer-events-none"
              style={{ background: breakdownStripAccent(slotKey) }}
            />
            {card && (
              <img
                src={card.imageArtCrop}
                alt=""
                aria-hidden
                className="absolute inset-0 w-full h-full object-cover pointer-events-none"
              />
            )}
            <div className="absolute inset-0 bg-black/55 pointer-events-none" />
            {gihwr !== null && (
              <span className="relative z-10 flex items-center justify-center h-full text-[7px] lg:text-[8px] font-mono font-semibold text-white/40 pointer-events-none select-none">
                {(gihwr * 100).toFixed(0)}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Layer 2: transparent hover targets — no overflow:hidden so tooltips escape upward */}
      <div
        className="absolute top-0 left-0 h-full flex gap-px"
        style={{ width: `${fillPct}%` }}
      >
        {activeContribs.map((seg, i) => {
          const isActive = touchIdx === i;
          return (
            <div
              key={seg.slotKey}
              className="group/seg relative h-full cursor-pointer"
              style={{ flexGrow: seg.points, flexBasis: 0 }}
              onTouchStart={(e) => {
                e.stopPropagation();
                setTouchIdx(isActive ? null : i);
              }}
              onTouchEnd={(e) => e.stopPropagation()}
            >
              {/* desktop: CSS hover — full card image preview */}
              <div className="absolute bottom-[calc(100%+7px)] left-1/2 -translate-x-1/2 z-50 pointer-events-none opacity-0 group-hover/seg:opacity-100 transition-opacity duration-100 hidden lg:block">
                <SegTooltipContent seg={seg} />
              </div>
              {/* mobile: tap-toggled */}
              {isActive && (
                <div className="absolute bottom-[calc(100%+7px)] left-1/2 -translate-x-1/2 z-50 pointer-events-none lg:hidden">
                  <SegTooltipContent seg={seg} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Your result ──────────────────────────────────────────────────────────────

const PODIUM: Record<number, { emoji: string; label: string; color: string }> = {
  1: { emoji: "🥇", label: "1st place", color: "#ffc63a" },
  2: { emoji: "🥈", label: "2nd place", color: "#c0c8d6" },
  3: { emoji: "🥉", label: "3rd place", color: "#c87941" },
};

function YourResultCard({
  ballot,
  total,
  crowdScore,
  bestScore,
}: {
  ballot: RankedBallot;
  total: number;
  crowdScore: number;
  bestScore: number;
}) {
  const { rank, score } = ballot;
  const pod = PODIUM[rank] ?? null;
  const vsCrowd = score - crowdScore;
  const vsBest = score - bestScore;
  const topPct = Math.max(1, Math.round((rank / total) * 100));

  const scoreColor = pod?.color ?? "#ffffff";
  const borderBg = pod ? `${pod.color}8c` : "#3b4458";

  // Bar positions: track scaled 0..bestScore
  const fillPct = bestScore > 0 ? (score / bestScore) * 100 : 0;
  const crowdPct = bestScore > 0 ? (crowdScore / bestScore) * 100 : 0;

  return (
    <div
      className="animate-fadeUpIn w-full"
      style={{ maxWidth: 720, clipPath: CHAMFER, background: borderBg, padding: 1 }}
    >
      <div className="bg-surface2" style={{ clipPath: CHAMFER }}>

        {/* Header: medal badge + ordinal */}
        <div className="flex items-center gap-3 px-4 sm:px-7 pt-4 sm:pt-5 pb-1">
          {pod && (
            <span
              className="font-display tracking-[0.12em] text-[12px] sm:text-[13px] inline-flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-sm"
              style={{ color: pod.color, background: `${pod.color}1a`, border: `1px solid ${pod.color}52` }}
            >
              {pod.emoji} {pod.label.toUpperCase()}
            </span>
          )}
          <span className="font-mono text-[12px] text-dim">#{rank} of {total}</span>
        </div>

        {/* Score hero */}
        <div className="px-4 sm:px-7 py-4 sm:py-5 text-center">
          <div
            className="font-mono tabular-nums leading-none"
            style={{ fontSize: "clamp(52px,14vw,80px)", color: scoreColor, textShadow: `0 0 56px ${scoreColor}60` }}
          >
            {score.toFixed(1)}
          </div>
          <div className="font-display tracking-[0.14em] sm:tracking-[0.16em] text-[10px] sm:text-[11px] text-muted mt-2">
            SCORE · GIH WIN RATE SUM
          </div>
          <div className="font-mono text-[12px] sm:text-[13px] text-subtle mt-1.5">top {topPct}%</div>
        </div>

        {/* Comparison bar */}
        <div className="px-4 sm:px-7 pb-5 sm:pb-7">
          {/* Labels above */}
          <div className="flex justify-between font-display tracking-[0.08em] sm:tracking-[0.1em] text-[10px] text-muted mb-1.5">
            <span>CROWD <span className="font-mono tabular-nums text-subtle">{crowdScore.toFixed(1)}</span></span>
            <span className="text-green">YOU <span className="font-mono tabular-nums">{score.toFixed(1)}</span></span>
            <span>BEST <span className="font-mono tabular-nums text-subtle">{bestScore.toFixed(1)}</span></span>
          </div>
          {/* Track */}
          <div className="h-1.5 bg-border rounded-sm overflow-visible relative">
            <div className="absolute inset-0 overflow-hidden rounded-sm">
              <div className="absolute top-0 left-0 bottom-0 bg-green" style={{ width: `${fillPct}%` }} />
            </div>
            <div className="absolute top-0 bottom-0 w-px bg-muted/70" style={{ left: `${crowdPct}%` }} />
          </div>
          {/* Deltas */}
          <div className="flex gap-5 mt-1.5 font-mono tabular-nums text-[11px]">
            <span className={vsCrowd >= 0 ? "text-green" : "text-red"}>
              {vsCrowd >= 0 ? "+" : ""}{vsCrowd.toFixed(1)} vs crowd
            </span>
            <span className="text-red">{vsBest.toFixed(1)} vs best</span>
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Champion spotlight ──────────────────────────────────────────────────────────

function WinningBallotTile({
  slotKey,
  label,
  cardName,
  card,
}: {
  slotKey: SlotKey;
  label: string;
  cardName: string | null;
  card: Card | undefined;
}) {
  const [touchOpen, setTouchOpen] = useState(false);
  const accent = SLOT_ACCENT[slotKey];

  return (
    <div className="group/wtile relative min-w-0">
      <div
        className="flex flex-col border border-t-0 border-border2 bg-surface overflow-hidden cursor-pointer"
        onTouchStart={(e) => {
          e.stopPropagation();
          setTouchOpen((o) => !o);
        }}
      >
        <div className="h-[3px] w-full shrink-0" style={{ background: accent }} />
        <div className="relative aspect-square bg-surface2 overflow-hidden">
          {card ? (
            <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-muted text-[10px] px-1 text-center">
              {cardName ?? "—"}
            </div>
          )}
        </div>
        <div className="px-1 py-1 min-w-0">
          <span className="text-subtle text-[9px] lg:text-[10px] truncate block" title={cardName ?? label}>
            {cardName ?? "—"}
          </span>
        </div>
      </div>

      {card && (
        <>
          <div className="absolute bottom-[calc(100%+7px)] left-1/2 -translate-x-1/2 z-50 pointer-events-none opacity-0 group-hover/wtile:opacity-100 transition-opacity duration-100 hidden lg:block">
            <img src={card.imageNormal} alt={card.name} className="w-[160px] rounded-sm border border-border2 shadow-xl" />
          </div>
          {touchOpen && (
            <div className="absolute bottom-[calc(100%+7px)] left-1/2 -translate-x-1/2 z-50 pointer-events-none lg:hidden">
              <img src={card.imageNormal} alt={card.name} className="w-[160px] rounded-sm border border-border2 shadow-xl" />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ChampionCard({
  ballot,
  total,
  isSelf,
  cardsByName,
}: {
  ballot: RankedBallot;
  total: number;
  isSelf: boolean;
  cardsByName: Map<string, Card>;
}) {
  const topPct = Math.max(1, Math.round((ballot.rank / total) * 100));

  const tiles = useMemo(
    () =>
      SLOTS.map((slot) => {
        const cardName = ballot.picks.get(slot.key) ?? null;
        const card = cardName ? cardsByName.get(cardName) : undefined;
        return { slotKey: slot.key, label: slot.label, cardName, card };
      }),
    [ballot, cardsByName],
  );

  return (
    <div
      className="animate-fadeUpIn w-full"
      style={{
        clipPath: CHAMFER,
        padding: 1,
        background: "linear-gradient(120deg, #ffc63a, #ffc63a55 35%, #3b4458 65%, #ffc63a44)",
        filter: "drop-shadow(0 0 28px #ffc63a2e)",
      }}
    >
      <div
        className="relative overflow-hidden bg-surface2 px-4 sm:px-6 pt-4 sm:pt-5 pb-4 sm:pb-5"
        style={{
          clipPath: CHAMFER,
          backgroundImage: "radial-gradient(120% 140% at 8% 0%, #ffc63a1c, transparent 45%)",
        }}
      >
        <div
          className="absolute -top-8 sm:-top-11 right-1 font-display leading-none pointer-events-none select-none"
          style={{ fontSize: "clamp(140px,32vw,230px)", color: "#ffc63a12" }}
        >
          1
        </div>

        <div className="relative flex flex-wrap items-center gap-3 sm:gap-4">
          {ballot.avatarUrl ? (
            <img
              src={ballot.avatarUrl}
              alt={ballot.name}
              className="w-14 h-14 sm:w-16 sm:h-16 rounded-full shrink-0 object-cover"
              style={{ boxShadow: "0 0 0 2px #1d2330, 0 0 0 4px #ffc63a, 0 0 24px #ffc63a66" }}
            />
          ) : (
            <div
              className="w-14 h-14 sm:w-16 sm:h-16 rounded-full shrink-0 bg-surface flex items-center justify-center text-[20px] sm:text-[24px] text-muted font-mono"
              style={{ boxShadow: "0 0 0 2px #1d2330, 0 0 0 4px #ffc63a, 0 0 24px #ffc63a66" }}
            >
              ?
            </div>
          )}

          <div className="flex-1 min-w-0">
            <div className="font-display tracking-[0.2em] sm:tracking-[0.22em] text-[13px] sm:text-[15px] text-gold">
              🥇 CHAMPION
            </div>
            <div className="text-[19px] sm:text-[26px] font-semibold leading-tight truncate">
              {ballot.name}
              {isSelf && (
                <span className="ml-2 text-[10px] font-normal text-subtle font-display tracking-widest align-middle">
                  YOU
                </span>
              )}
            </div>
            <div className="text-[11px] sm:text-[12.5px] text-muted mt-0.5">
              Top {topPct}% of {total} ballots
            </div>
          </div>

          <div className="hidden lg:block text-right shrink-0">
            <div
              className="font-mono tabular-nums text-[52px] font-bold leading-none text-gold"
              style={{ textShadow: "0 0 56px #ffc63ab0, 0 0 18px #ffc63a50" }}
            >
              {ballot.score.toFixed(1)}
            </div>
            <div className="font-display tracking-[0.2em] text-[12px] text-muted mt-1">FINAL SCORE</div>
          </div>
        </div>

        <div className="lg:hidden mt-3 flex items-baseline gap-2.5">
          <div
            className="font-mono tabular-nums text-[40px] font-bold leading-none text-gold"
            style={{ textShadow: "0 0 56px #ffc63ab0, 0 0 18px #ffc63a50" }}
          >
            {ballot.score.toFixed(1)}
          </div>
          <div className="font-display tracking-[0.2em] text-[11px] text-muted">FINAL SCORE</div>
        </div>

        <div className="font-display tracking-[0.2em] text-[11px] sm:text-[12px] text-muted mt-4 mb-1.5">
          THE WINNING BALLOT
        </div>
        <div className="grid grid-cols-4 lg:grid-cols-8 gap-1.5">
          {tiles.map((t) => (
            <WinningBallotTile key={t.slotKey} {...t} />
          ))}
        </div>
      </div>
    </div>
  );
}

const MEDAL_ROW_STYLE: Record<2 | 3, { color: string; label: string; tint: string }> = {
  2: { color: "#c0c8d6", label: "2ND", tint: "linear-gradient(90deg, #c0c8d612, transparent 55%)" },
  3: { color: "#c87941", label: "3RD", tint: "linear-gradient(90deg, #c8794112, transparent 55%)" },
};

function MedalRow({
  ballot,
  setCode,
  isSelf,
  maxScore,
  cardsByName,
  ratingsByName,
}: {
  ballot: RankedBallot;
  setCode: string;
  isSelf: boolean;
  maxScore: number;
  cardsByName: Map<string, Card>;
  ratingsByName: Map<string, CardRating>;
}) {
  const [expanded, setExpanded] = useState(false);
  const entries = useMemo(
    () => (expanded ? ballotToEntries(ballot, setCode, ratingsByName) : []),
    [expanded, ballot, setCode, ratingsByName],
  );
  const medal = MEDAL_ROW_STYLE[ballot.rank as 2 | 3];

  return (
    <div
      className={`border-b border-border2 last:border-b-0 ${isSelf ? "bg-white/[0.04]" : ""}`}
      style={{ boxShadow: `inset 3px 0 0 ${medal.color}`, backgroundImage: isSelf ? undefined : medal.tint }}
    >
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2.5 lg:py-3 text-left cursor-pointer bg-transparent border-0"
      >
        <span
          className="w-7 lg:w-8 shrink-0 text-right font-display tracking-[0.06em] text-[15px] lg:text-[17px]"
          style={{ color: medal.color }}
        >
          {medal.label}
        </span>

        {ballot.avatarUrl ? (
          <img
            src={ballot.avatarUrl}
            alt={ballot.name}
            className="w-6 h-6 lg:w-7 lg:h-7 rounded-full shrink-0 object-cover"
            style={{ boxShadow: `0 0 0 1.5px ${medal.color}` }}
          />
        ) : (
          <div
            className="w-6 h-6 lg:w-7 lg:h-7 rounded-full shrink-0 bg-surface flex items-center justify-center text-[10px] lg:text-[11px] text-muted font-mono"
            style={{ boxShadow: `0 0 0 1.5px ${medal.color}` }}
          >
            ?
          </div>
        )}

        <span
          className={`flex-1 min-w-0 lg:flex-none lg:w-[150px] lg:shrink-0 text-[14px] lg:text-[15px] truncate ${isSelf ? "text-white font-semibold" : "text-text"}`}
        >
          {ballot.name}
          {isSelf && (
            <span className="ml-2 text-[10px] font-normal text-subtle font-display tracking-widest">YOU</span>
          )}
        </span>

        <ContributionBar
          ballot={ballot}
          maxScore={maxScore}
          ratingsByName={ratingsByName}
          cardsByName={cardsByName}
        />

        <span
          className="font-mono tabular-nums text-[13px] lg:text-[14px] font-semibold shrink-0"
          style={{ color: medal.color }}
        >
          {ballot.score.toFixed(1)}
        </span>

        <ChevronDown
          size={14}
          className={`shrink-0 text-muted transition-transform duration-150 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="px-3 lg:px-4 pb-4 pt-1">
          <PickGrid entries={entries} cardsByName={cardsByName} />
        </div>
      )}
    </div>
  );
}

// ── Leaderboard ───────────────────────────────────────────────────────────────

function LeaderboardRow({
  ballot,
  setCode,
  isSelf,
  maxScore,
  cardsByName,
  ratingsByName,
}: {
  ballot: RankedBallot;
  setCode: string;
  isSelf: boolean;
  maxScore: number;
  cardsByName: Map<string, Card>;
  ratingsByName: Map<string, CardRating>;
}) {
  const [expanded, setExpanded] = useState(false);
  const entries = useMemo(
    () => (expanded ? ballotToEntries(ballot, setCode, ratingsByName) : []),
    [expanded, ballot, setCode, ratingsByName],
  );

  return (
    <div className={`border-b border-border2 last:border-b-0 ${isSelf ? "bg-white/[0.04]" : ""}`}>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 lg:gap-3 px-3 lg:px-4 py-2.5 lg:py-3 text-left cursor-pointer bg-transparent border-0"
      >
        <span className="w-7 lg:w-8 shrink-0 text-right font-mono tabular-nums text-[12px] lg:text-[13px] text-muted">
          #{ballot.rank}
        </span>

        {ballot.avatarUrl ? (
          <img
            src={ballot.avatarUrl}
            alt={ballot.name}
            className="w-6 h-6 lg:w-7 lg:h-7 rounded-full shrink-0 object-cover"
          />
        ) : (
          <div className="w-6 h-6 lg:w-7 lg:h-7 rounded-full shrink-0 bg-surface flex items-center justify-center text-[10px] lg:text-[11px] text-muted font-mono">
            ?
          </div>
        )}

        <span
          className={`flex-1 min-w-0 lg:flex-none lg:w-[150px] lg:shrink-0 text-[14px] lg:text-[15px] truncate ${isSelf ? "text-white font-semibold" : "text-text"}`}
        >
          {ballot.name}
          {isSelf && (
            <span className="ml-2 text-[10px] font-normal text-subtle font-display tracking-widest">YOU</span>
          )}
        </span>

        {/* bar lives here in the flex row — self-stretch fills full row height */}
        <ContributionBar
          ballot={ballot}
          maxScore={maxScore}
          ratingsByName={ratingsByName}
          cardsByName={cardsByName}
        />

        <span className="font-mono tabular-nums text-[13px] lg:text-[14px] text-subtle shrink-0">
          {ballot.score.toFixed(1)}
        </span>

        <ChevronDown
          size={14}
          className={`shrink-0 text-muted transition-transform duration-150 ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="px-3 lg:px-4 pb-4 pt-1">
          <PickGrid entries={entries} cardsByName={cardsByName} />
        </div>
      )}
    </div>
  );
}

const COLLAPSED_COUNT = 3;

function Leaderboard({
  rankedBallots,
  setCode,
  userBallotId,
  cardsByName,
  ratingsByName,
  mode = "full",
  onSeeAll,
  spotlight = false,
}: {
  rankedBallots: RankedBallot[];
  setCode: string;
  userBallotId: number | null;
  cardsByName: Map<string, Card>;
  ratingsByName: Map<string, CardRating>;
  mode?: "peek" | "full";
  onSeeAll?: () => void;
  spotlight?: boolean;
}) {
  const maxScore = rankedBallots[0]?.score ?? 1;
  const isPeek = mode === "peek";
  const hasMore = rankedBallots.length > COLLAPSED_COUNT;
  const useSpotlight = spotlight && isPeek;

  const visible = useMemo(() => {
    if (!isPeek || !hasMore) return rankedBallots;
    const peek = rankedBallots.slice(0, COLLAPSED_COUNT);
    // Pin the user's own row if it falls outside the peek window
    if (userBallotId !== null) {
      const selfInPeek = peek.some((b) => b.ballotId === userBallotId);
      if (!selfInPeek) {
        const selfBallot = rankedBallots.find((b) => b.ballotId === userBallotId);
        if (selfBallot) return [...peek, selfBallot];
      }
    }
    return peek;
  }, [isPeek, hasMore, rankedBallots, userBallotId]);

  const champion = useSpotlight ? visible.find((b) => b.rank === 1) ?? null : null;
  const rows = champion ? visible.filter((b) => b.ballotId !== champion.ballotId) : visible;

  return (
    <div className="flex flex-col gap-3">
      {champion && (
        <ChampionCard
          ballot={champion}
          total={rankedBallots.length}
          isSelf={champion.ballotId === userBallotId}
          cardsByName={cardsByName}
        />
      )}
      <div>
        <div className="relative">
          <div className="border-t border-border2 bg-surface2">
            {rows.map((ballot) =>
              useSpotlight && (ballot.rank === 2 || ballot.rank === 3) ? (
                <MedalRow
                  key={ballot.ballotId}
                  ballot={ballot}
                  setCode={setCode}
                  isSelf={ballot.ballotId === userBallotId}
                  maxScore={maxScore}
                  cardsByName={cardsByName}
                  ratingsByName={ratingsByName}
                />
              ) : (
                <LeaderboardRow
                  key={ballot.ballotId}
                  ballot={ballot}
                  setCode={setCode}
                  isSelf={ballot.ballotId === userBallotId}
                  maxScore={maxScore}
                  cardsByName={cardsByName}
                  ratingsByName={ratingsByName}
                />
              ),
            )}
          </div>
          {/* Peek fade — only when in peek mode and there are hidden rows */}
          {isPeek && hasMore && (
            <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-surface2 to-transparent pointer-events-none" />
          )}
        </div>
        {isPeek && hasMore && onSeeAll && (
          <button
            type="button"
            onClick={onSeeAll}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-surface2 border-t-0 border border-border2 text-subtle hover:text-text transition-colors"
          >
            <span className="font-display tracking-[0.14em] text-[13px]">
              SEE ALL {rankedBallots.length} STANDINGS →
            </span>
          </button>
        )}
      </div>
    </div>
  );
}

// ── Highlights reel ───────────────────────────────────────────────────────────

function HighlightTile({
  gap,
  cardsByName,
}: {
  gap: SlotRankGap;
  cardsByName: Map<string, Card>;
}) {
  const card = cardsByName.get(gap.cardName);
  const isOverrated = gap.kind === "overrated";
  const accent = isOverrated ? "#ff6b6b" : "#2ee85c";
  const label = isOverrated ? "OVERRATED" : "UNDERRATED";
  const rankText = isOverrated
    ? `#${gap.popularityRank} popular → #${gap.gihwrRank} GIH WR`
    : `#${gap.gihwrRank} GIH WR → #${gap.popularityRank} popular`;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="inline-block font-display tracking-[0.14em] uppercase text-[11px] leading-none px-2 py-1 rounded-sm"
        style={{ background: `${accent}22`, color: accent }}
      >
        {label}
      </div>

      {card ? (
        <div className="relative w-[120px] h-[120px] rounded overflow-hidden">
          <img
            src={card.imageArtCrop}
            alt={card.name}
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 bg-black/60 px-1.5 py-1">
            <div className="text-white text-[11px] font-semibold leading-snug truncate">{card.name}</div>
            <div className="text-dim text-[10px] font-mono">{gap.slotLabel}</div>
          </div>
        </div>
      ) : (
        <div className="w-[120px] h-[120px] bg-surface2 border border-border2 rounded flex items-center justify-center text-[13px] text-muted">
          {gap.cardName}
        </div>
      )}

      <p className="text-[11px] text-dim text-center font-mono max-w-[130px]">{rankText}</p>
    </div>
  );
}

function HighlightsReel({
  highlights,
  cardsByName,
}: {
  highlights: SlotRankGap[];
  cardsByName: Map<string, Card>;
}) {
  if (highlights.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-center">
        <SectionLabel size={22} className="text-white">HIGHLIGHTS</SectionLabel>
      </div>
      <div className="flex flex-wrap justify-center gap-6">
        {highlights.map((gap) => (
          <HighlightTile key={`${gap.slot}-${gap.cardName}`} gap={gap} cardsByName={cardsByName} />
        ))}
      </div>
    </div>
  );
}

// ── Orchestrator ──────────────────────────────────────────────────────────────

export function FinalResults({
  ratingsSnapshot,
  pickStats,
  ballots,
  cards,
  cardsByName,
  picksBySlot,
  user,
  signIn,
  hasParticipated,
}: {
  ratingsSnapshot: RatingsSnapshot;
  pickStats: P0P1PickStat[];
  ballots: P0P1BallotRow[];
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
  const rankedBallots = useMemo(() => {
    const grouped = groupBallotRows(ballots);
    return rankBallots(grouped, ratingsByName);
  }, [ballots, ratingsByName]);
  const highlights = useMemo(
    () => slotRankGaps(pickStats, SLOTS, ratingsByName, HIGHLIGHTS_COUNT),
    [pickStats, ratingsByName],
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

  const userBallot = useMemo(
    () => (showYourPicks ? findUserBallot(rankedBallots, picksBySlot) : null),
    [showYourPicks, rankedBallots, picksBySlot],
  );

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
  const bounds = useMemo(() => gihwrBounds(pickStats, ratingsByName), [pickStats, ratingsByName]);

  const onTileOpen = (slotKey: SlotKey) => {
    const idx = SLOTS.findIndex((s) => s.key === slotKey);
    if (idx !== -1) pager.open(idx);
  };

  const yourCardBySlot = useMemo(
    () => (showYourPicks ? (picksBySlot as Map<SlotKey, string>) : new Map<SlotKey, string>()),
    [showYourPicks, picksBySlot],
  );

  // Keep "your picks" score visible even when no ratingsSnapshot score — show raw
  const displayScore = yourScore ?? 0;

  const [searchParams, setSearchParams] = useSearchParams();
  const TABS = [
    { id: "overview", label: "OVERVIEW" },
    { id: "results", label: "FULL RESULTS" },
    { id: "breakdown", label: "BREAKDOWN" },
  ] as const;
  type TabId = typeof TABS[number]["id"];
  const rawTab = searchParams.get("tab") as TabId | null;
  const activeTab: TabId = TABS.some((t) => t.id === rawTab) ? rawTab! : "overview";

  const goToTab = (id: TabId) =>
    setSearchParams({ tab: id }, { replace: true });

  const statsBlock = useMemo(() => {
    if (rankedBallots.length === 0) return null;
    const avg = rankedBallots.reduce((s, b) => s + b.score, 0) / rankedBallots.length;
    const top = rankedBallots[0];
    return { count: rankedBallots.length, avg, top };
  }, [rankedBallots]);

  return (
    <div className="flex flex-col gap-6">
      {dateCaption && (
        <p className="text-center text-dim font-mono text-[11px] tracking-widest uppercase">
          17lands data through {dateCaption} · final results
        </p>
      )}

      {/* Sub-tab bar */}
      <div className="flex items-center gap-4">
        <div className="flex gap-1 bg-surface2 border border-border rounded-md p-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => goToTab(tab.id)}
              className={`font-display tracking-[0.14em] text-[13px] px-4 py-1.5 rounded transition-colors border-0 cursor-pointer ${
                activeTab === tab.id
                  ? "bg-green text-bg"
                  : "bg-transparent text-muted hover:text-text"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {rankedBallots.length > 0 && (
          <span className="font-mono text-[11px] text-dim">
            {rankedBallots.length} participants
          </span>
        )}
      </div>

      {/* ── OVERVIEW ─────────────────────────────────────────────────── */}
      {activeTab === "overview" && (
        <div className="flex flex-col gap-8">
          {/* Your result */}
          {showYourPicks && userBallot && (
            <div className="flex justify-center">
              <YourResultCard ballot={userBallot} total={rankedBallots.length} crowdScore={crowdTeam.score} bestScore={bestTeam.score} />
            </div>
          )}
          {showYourPicks && !userBallot && (
            <div className="flex justify-center">
              <div className="flex flex-col items-center gap-1 py-3 px-6 bg-surface2 border border-border2 rounded-sm">
                <div className="font-display tracking-[0.18em] text-[13px] text-subtle uppercase">Your result</div>
                <div className="font-mono tabular-nums text-[28px] text-white mt-1">{displayScore.toFixed(1)}</div>
              </div>
            </div>
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

          {/* Stat tiles */}
          {statsBlock && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-surface2 border border-border2 rounded-sm px-4 py-3">
                <div className="font-display tracking-[0.14em] text-[11px] text-muted uppercase mb-1">Participants</div>
                <div className="font-mono tabular-nums text-[22px] text-text font-semibold">{statsBlock.count}</div>
              </div>
              <div className="bg-surface2 border border-border2 rounded-sm px-4 py-3">
                <div className="font-display tracking-[0.14em] text-[11px] text-muted uppercase mb-1">Avg score</div>
                <div className="font-mono tabular-nums text-[22px] text-text font-semibold">{statsBlock.avg.toFixed(1)}</div>
              </div>
              <div className="bg-surface2 border border-border2 rounded-sm px-4 py-3">
                <div className="font-display tracking-[0.14em] text-[11px] text-muted uppercase mb-1">Top score</div>
                <div className="font-mono tabular-nums text-[22px] font-semibold" style={{ color: "#ffc63a" }}>
                  {statsBlock.top.score.toFixed(1)}
                </div>
                <div className="text-[11px] text-muted mt-0.5 truncate">{statsBlock.top.name}</div>
              </div>
            </div>
          )}

          {/* Top-3 standings peek */}
          {rankedBallots.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <SectionLabel size={16} className="text-white">TOP STANDINGS</SectionLabel>
                <button
                  type="button"
                  onClick={() => goToTab("results")}
                  className="font-display tracking-[0.12em] text-[11px] px-3 py-1 bg-transparent border border-border2 text-muted hover:text-text rounded transition-colors cursor-pointer"
                >
                  SEE ALL →
                </button>
              </div>
              <Leaderboard
                rankedBallots={rankedBallots}
                setCode={setCode}
                userBallotId={userBallot?.ballotId ?? null}
                cardsByName={cardsByName}
                ratingsByName={ratingsByName}
                mode="peek"
                onSeeAll={() => goToTab("results")}
                spotlight
              />
            </div>
          )}

          {/* Highlights reel */}
          <HighlightsReel highlights={highlights} cardsByName={cardsByName} />
        </div>
      )}

      {/* ── FULL RESULTS ─────────────────────────────────────────────── */}
      {activeTab === "results" && (
        <div className="flex flex-col gap-8">
          {rankedBallots.length > 0 && (
            <div className="flex flex-col gap-3">
              <SectionLabel size={16} className="text-white">STANDINGS</SectionLabel>
              <Leaderboard
                rankedBallots={rankedBallots}
                setCode={setCode}
                userBallotId={userBallot?.ballotId ?? null}
                cardsByName={cardsByName}
                ratingsByName={ratingsByName}
                mode="full"
              />
            </div>
          )}

          {/* Per-slot 3-way comparison — yours / crowd / best, keyed on GIHWR */}
          <div className="flex flex-col gap-3">
            <div className="flex items-baseline justify-center gap-3 mb-2">
              <SectionLabel size={22} className="text-white">YOUR PICKS</SectionLabel>
              {showYourPicks && (
                <span className="font-mono tabular-nums text-[18px] text-subtle">
                  {displayScore.toFixed(1)}
                </span>
              )}
            </div>
            {showYourPicks && (
              <PickGrid entries={yourEntries} cardsByName={cardsByName} onTileOpen={onTileOpen} />
            )}
            <div className="flex items-baseline justify-center gap-3 mb-2 mt-4">
              <SectionLabel size={22} className="text-white">CROWD TEAM</SectionLabel>
              <span className="font-mono tabular-nums text-[18px] text-subtle">
                {crowdTeam.score.toFixed(1)}
              </span>
            </div>
            <PickGrid entries={crowdEntries} cardsByName={cardsByName} onTileOpen={onTileOpen} />
            <div className="flex items-baseline justify-center gap-3 mb-2 mt-4">
              <SectionLabel size={22} className="text-white">BEST POSSIBLE</SectionLabel>
              <span className="font-mono tabular-nums text-[18px] text-subtle">
                {bestTeam.score.toFixed(1)}
              </span>
            </div>
            <PickGrid entries={bestEntries} cardsByName={cardsByName} onTileOpen={onTileOpen} />
          </div>

          <MidwayVersusModal pager={pager} bounds={bounds} />
        </div>
      )}

      {/* ── BREAKDOWN ────────────────────────────────────────────────── */}
      {activeTab === "breakdown" && (
        <MidwayBreakdownList
          cards={cards}
          cardsByName={cardsByName}
          ratingsByName={ratingsByName}
          yourCardBySlot={yourCardBySlot}
          pickStats={pickStats}
          bounds={bounds}
        />
      )}
    </div>
  );
}
