import { useEffect, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, X, ZoomIn, ZoomOut } from "lucide-react";
import { ArrowRight, GiRoundTable, ImageIcon, LuScrollText, TbCards } from "../Icons";
import { ChamferedButton } from "../ChamferedButton";
import { Pips } from "../ManaPips";
import { Record } from "../Record";
import { cn } from "../../lib/utils";
import { useIsMobile } from "../../lib/use-is-mobile";
import {
  isDiscordCdnUrl,
  isDiscordUrlFresh,
  refreshDeckUrl,
} from "../../data/refresh-deck-url";
import type { Mainboard } from "../../types/leaderboard";

export const BREAKDOWN_CAPTION = "Seats, logs & replays";

export interface DeckLike {
  eventId?: string;
  displayName: string;
  participantDisplayName?: string;
  deckColors: string | null;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption?: string | null;
  mainboard?: Mainboard | null;
  record?: string | null;
  draftLogUrl?: string | null;
}

type DeckTab = "screenshot" | "decklist";

interface Props {
  participant: DeckLike;
  breakdownHref?: string;
  onClose: () => void;
  onPrev?: () => void;
  onNext?: () => void;
}

export function DeckScreenshotModal({ participant, breakdownHref, onClose, onPrev, onNext }: Props) {
  const isMobile = useIsMobile();

  const hasScreenshot = participant.deckScreenshotUrl !== null;
  const hasDecklist = (participant.mainboard?.cards.length ?? 0) > 0;
  const deckKey = `${participant.eventId ?? ""}::${participant.participantDisplayName ?? participant.displayName}`;
  const [tab, setTab] = useState<DeckTab>("screenshot");
  const effectiveTab: DeckTab =
    hasScreenshot && hasDecklist ? tab : hasDecklist ? "decklist" : "screenshot";

  const needsRefresh = useMemo(() => {
    const url = participant.deckScreenshotUrl;
    if (!url || !participant.eventId) return false;
    return isDiscordCdnUrl(url) && !isDiscordUrlFresh(url);
  }, [participant.deckScreenshotUrl, participant.eventId]);

  const [resolvedUrl, setResolvedUrl] = useState<string | null>(
    needsRefresh ? null : participant.deckScreenshotUrl,
  );
  const [isResolving, setIsResolving] = useState(needsRefresh);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const [zoomed, setZoomed] = useState(true);

  useEffect(() => {
    setZoomed(true);
    setResolvedUrl(needsRefresh ? null : participant.deckScreenshotUrl);
    setIsResolving(needsRefresh);
  }, [participant.deckScreenshotUrl, needsRefresh]);

  useEffect(() => {
    setImgLoaded(false);
    setImgFailed(false);
    if (!resolvedUrl) return;
    const preloader = new Image();
    preloader.onload = () => setImgLoaded(true);
    preloader.onerror = () => setImgFailed(true);
    preloader.src = resolvedUrl;
  }, [resolvedUrl]);

  const showSkeleton = isResolving || (resolvedUrl !== null && !imgLoaded && !imgFailed);

  useEffect(() => {
    if (!needsRefresh || !participant.eventId) return;
    const lookupName = participant.participantDisplayName ?? participant.displayName;
    let cancelled = false;
    refreshDeckUrl(participant.eventId, lookupName)
      .then((url) => {
        if (cancelled) return;
        setResolvedUrl(url ?? participant.deckScreenshotUrl);
      })
      .finally(() => {
        if (!cancelled) setIsResolving(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    needsRefresh,
    participant.eventId,
    participant.displayName,
    participant.participantDisplayName,
    participant.deckScreenshotUrl,
  ]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "ArrowLeft" && onPrev) {
        e.preventDefault();
        onPrev();
      } else if (e.key === "ArrowRight" && onNext) {
        e.preventDefault();
        onNext();
      }
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose, onPrev, onNext]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex flex-col items-center bg-black/80 backdrop-blur-sm animate-fadeIn px-[4px] md:px-6 pt-28 pb-6 lg:pt-28 lg:pb-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${participant.displayName}'s deck`}
    >
      <div
        className="relative bg-surface border border-border w-full max-w-[1400px] h-[70vh] shrink-0 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 lg:gap-6 pl-9 pr-5 py-3 border-b border-border shrink-0">
          <Pips colors={participant.deckColors ?? ""} size={18} />
          <span
            className="font-display text-text truncate flex-1 text-center lg:text-left"
            style={{ fontSize: 26, lineHeight: 1, letterSpacing: "0.04em", fontFamily: "'Bebas Neue', sans-serif", paddingTop: 4 }}
          >
            {participant.displayName}
          </span>
          {participant.record && (
            <Record
              wins={Number(participant.record.split("-")[0] || 0)}
              losses={Number(participant.record.split("-")[1] || 0)}
              className="mono text-[20px] shrink-0"
            />
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer shrink-0"
          >
            <X size={18} />
          </button>
        </header>

        <div className="flex-1 min-h-0 overflow-hidden">
          <div key={deckKey} className="h-full animate-fadeIn">
          {effectiveTab === "decklist" && participant.mainboard ? (
            <DecklistView mainboard={participant.mainboard} />
          ) : showSkeleton ? (
            <div className="h-full p-4 md:p-5">
              <div className="w-full h-full bg-surface2 animate-pulse" />
            </div>
          ) : imgFailed ? (
            <div className="h-full flex items-center justify-center px-5 text-center text-muted font-body">
              Deck screenshot failed to load
            </div>
          ) : resolvedUrl ? (
            isMobile ? (
              <div className="relative h-full">
                {zoomed ? (
                  <div className="h-full overflow-x-auto overflow-y-hidden themed-scrollbar">
                    <img
                      src={resolvedUrl}
                      alt={`${participant.displayName} deck screenshot`}
                      className="block h-full w-auto max-w-none select-none"
                      draggable={false}
                    />
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center overflow-hidden">
                    <img
                      src={resolvedUrl}
                      alt={`${participant.displayName} deck screenshot`}
                      className="block max-h-full max-w-full w-auto h-auto select-none"
                      draggable={false}
                    />
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => setZoomed((z) => !z)}
                  aria-label={zoomed ? "Fit deck to screen" : "Zoom deck"}
                  className="absolute left-2 bottom-2 z-10 inline-flex items-center gap-1.5 rounded bg-bg/85 border border-border text-text px-2.5 py-1.5 font-display tracking-[0.14em] text-[11px] cursor-pointer backdrop-blur-sm"
                >
                  {zoomed ? <ZoomOut size={13} /> : <ZoomIn size={13} />}
                  {zoomed ? "ZOOM OUT" : "ZOOM IN"}
                </button>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center overflow-hidden px-4 py-6">
                <img
                  src={resolvedUrl}
                  alt={`${participant.displayName} deck screenshot`}
                  className="block max-h-full max-w-full w-auto h-auto select-none"
                  draggable={false}
                />
              </div>
            )
          ) : (
            <div className="h-full flex items-center justify-center px-5 text-center text-muted font-body">
              No deck screenshot available
            </div>
          )}
          </div>
        </div>

        {breakdownHref && (
          <Link to={breakdownHref} className="hidden lg:block no-underline border-t border-border shrink-0">
            <div className="flex items-center justify-between gap-4 px-4 py-3 bg-surface hover:bg-green/5 transition-colors cursor-pointer">
              {participant.deckScreenshotCaption ? (
                <span className="text-muted text-[15px] font-body italic leading-snug min-w-0 truncate pr-1 pl-5">
                  {participant.deckScreenshotCaption}
                </span>
              ) : (
                <span className="pl-5" />
              )}
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-muted text-[13px] font-body">
                  {BREAKDOWN_CAPTION}
                </span>
                <ChamferedButton>
                  <span className="inline-flex items-center gap-2">
                    <GiRoundTable size={30} className="-my-[6px]" />
                    VIEW BREAKDOWN
                     <ArrowRight size={14} />
                  </span>
                </ChamferedButton>
              </div>
            </div>
          </Link>
        )}
        {participant.deckScreenshotCaption && (
          <div
            className={cn(
              "pl-9 pr-5 py-4 text-muted text-[15px] font-body italic leading-snug border-t border-border shrink-0 bg-surface",
              breakdownHref && "lg:hidden",
            )}
          >
            {participant.deckScreenshotCaption}
          </div>
        )}
        {effectiveTab === "decklist" && (participant.mainboard?.sideboard.length ?? 0) > 0 && (
          <div className="border-t border-border shrink-0 bg-surface pl-9 pr-5 py-3">
            <div className="font-display tracking-[0.16em] text-muted leading-none mb-2" style={{ fontSize: 13 }}>
              SIDEBOARD
            </div>
            <div className="flex gap-2 overflow-x-auto themed-scrollbar pb-1">
              {participant.mainboard!.sideboard.map((card) => (
                <SideboardCard key={`${card.name}-${card.cn}`} card={card} deckSet={participant.mainboard!.set} />
              ))}
            </div>
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0 w-full max-w-[1400px] flex flex-col items-center justify-center gap-10 px-4 md:px-0">
        <div
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 w-full lg:w-auto flex items-center justify-between gap-2 lg:gap-4 rounded-2xl bg-surface border border-border shadow-lg px-3 py-2 lg:px-4"
        >
          {onPrev ? <PanelChevron side="left" onClick={onPrev} /> : <span className="w-10 shrink-0" />}
          <div className="flex items-center gap-1.5">
            <PanelTab
              active={effectiveTab === "screenshot"}
              disabled={!hasScreenshot}
              onClick={() => setTab("screenshot")}
              icon={<ImageIcon size={16} />}
            >
              IMAGE
            </PanelTab>
            <PanelTab
              active={effectiveTab === "decklist"}
              disabled={!hasDecklist}
              onClick={() => setTab("decklist")}
              icon={<TbCards size={17} />}
            >
              <span className="lg:hidden">POOL</span>
              <span className="hidden lg:inline">CARD POOL</span>
            </PanelTab>
            <PanelTab
              disabled={!participant.draftLogUrl}
              onClick={
                participant.draftLogUrl
                  ? () => window.open(participant.draftLogUrl!, "_blank", "noopener,noreferrer")
                  : undefined
              }
              icon={<LuScrollText size={16} />}
            >
              <span className="lg:hidden">LOG</span>
              <span className="hidden lg:inline">DRAFT LOG</span>
            </PanelTab>
          </div>
          {onNext ? <PanelChevron side="right" onClick={onNext} /> : <span className="w-10 shrink-0" />}
        </div>
        {breakdownHref && (
          <Link
            to={breakdownHref}
            onClick={(e) => e.stopPropagation()}
            aria-label="View breakdown"
            className="lg:hidden self-end inline-flex items-center gap-1.5 pr-1 text-green hover:text-green/80 no-underline font-display tracking-[0.18em] leading-none"
            style={{ fontSize: 13 }}
          >
            VIEW BREAKDOWN
            <ArrowRight size={13} />
          </Link>
        )}
      </div>
    </div>,
    document.body,
  );
}

function PanelChevron({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const Chevron = side === "left" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      aria-label={side === "left" ? "Previous deck" : "Next deck"}
      className="shrink-0 inline-flex items-center justify-center w-10 h-10 rounded-full bg-surface2 border border-border text-green/90 hover:text-green hover:border-green/50 transition-colors cursor-pointer outline-none focus:outline-none focus-visible:outline-none"
    >
      <Chevron size={24} strokeWidth={2.5} />
    </button>
  );
}

function PanelTab({
  active = false,
  onClick,
  disabled = false,
  icon,
  children,
}: {
  active?: boolean;
  onClick?: () => void;
  disabled?: boolean;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-2 lg:px-4 lg:py-2.5 font-display tracking-[0.14em] leading-none transition-colors",
        "outline-none focus:outline-none focus-visible:outline-none",
        disabled
          ? "bg-surface2 text-subtle border-border opacity-50 cursor-not-allowed"
          : active
            ? "bg-green/15 text-green border-green/50 cursor-pointer"
            : "bg-surface2 text-muted border-border hover:text-text cursor-pointer",
      )}
      style={{ fontSize: 14 }}
    >
      <span className="relative inline-flex items-center justify-center">
        {icon}
        {disabled && (
          <span
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/2 h-[1.5px] w-[150%] -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-full bg-current"
          />
        )}
      </span>
      {children}
    </button>
  );
}

type DeckCard = Mainboard["cards"][number];

const STRIP_H = 36;
const COL_MIN = 132;
const COL_MAX = 220;

const COLOR_RANK: Record<string, number> = { W: 0, U: 1, B: 2, R: 3, G: 4 };

function isLand(type: string | null): boolean {
  return /land/i.test(type ?? "");
}

function colorSortKey(colors: string[]): number {
  if (colors.length === 0) return 7;
  if (colors.length > 1) return 5;
  return COLOR_RANK[colors[0]] ?? 6;
}

function byColorThenName(a: DeckCard, b: DeckCard): number {
  return colorSortKey(a.colors ?? []) - colorSortKey(b.colors ?? []) || a.name.localeCompare(b.name);
}

function scryfallImageUrl(set: string, collectorNumber: string): string {
  return `https://api.scryfall.com/cards/${set.toLowerCase()}/${encodeURIComponent(collectorNumber)}?format=image&version=normal`;
}

function DecklistView({ mainboard }: { mainboard: Mainboard }) {
  const { mvPiles, lands } = useMemo(() => {
    const landCards: DeckCard[] = [];
    const byCmc = new Map<number, DeckCard[]>();
    for (const card of mainboard.cards) {
      if (isLand(card.type)) {
        landCards.push(card);
        continue;
      }
      const cmc = card.cmc ?? 0;
      const pile = byCmc.get(cmc);
      if (pile) {
        pile.push(card);
      } else {
        byCmc.set(cmc, [card]);
      }
    }
    const piles = [...byCmc.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([cmc, cards]) => ({ cmc, cards: cards.slice().sort(byColorThenName) }));
    return { mvPiles: piles, lands: landCards.slice().sort(byColorThenName) };
  }, [mainboard]);

  return (
    <div className="h-full overflow-auto themed-scrollbar px-4 md:px-5 py-5">
      <div className="flex gap-2 md:gap-3 items-start">
        {mvPiles.map((pile) => (
          <Pile key={pile.cmc} cards={pile.cards} deckSet={mainboard.set} />
        ))}
        {lands.length > 0 && <Pile cards={lands} deckSet={mainboard.set} />}
      </div>
    </div>
  );
}

function Pile({ cards, deckSet }: { cards: DeckCard[]; deckSet: string | null }) {
  return (
    <div className="flex flex-col flex-1" style={{ minWidth: COL_MIN, maxWidth: COL_MAX }}>
      {cards.map((card, i) => (
        <StackedCard key={`${card.name}-${card.cn}`} card={card} deckSet={deckSet} reveal={i < cards.length - 1} />
      ))}
    </div>
  );
}

function StackedCard({ card, deckSet, reveal }: { card: DeckCard; deckSet: string | null; reveal: boolean }) {
  const [failed, setFailed] = useState(false);
  const set = card.set ?? deckSet;
  const src = set && card.cn ? scryfallImageUrl(set, card.cn) : null;
  const count = card.count ?? 1;
  return (
    <div
      className={cn(
        "relative w-full overflow-hidden rounded-[5px] shadow-[0_-1px_4px_rgba(0,0,0,0.45)]",
        !reveal && "aspect-[488/680]",
      )}
      style={reveal ? { height: STRIP_H } : undefined}
    >
      {src && !failed ? (
        <img
          src={src}
          alt={card.name}
          loading="lazy"
          onError={() => setFailed(true)}
          className="block w-full h-auto"
          draggable={false}
        />
      ) : (
        <div className="w-full aspect-[488/680] bg-surface2 border border-border flex items-start p-2">
          <span className="font-body text-subtle leading-tight" style={{ fontSize: 12 }}>{card.name}</span>
        </div>
      )}
      {count > 1 && <CountBadge n={count} />}
    </div>
  );
}

function CountBadge({ n }: { n: number }) {
  return (
    <span
      className="absolute right-1.5 inline-flex items-center justify-center bg-black/85 text-white font-display tabular-nums rounded px-2 leading-none"
      style={{ fontSize: 16, height: 26, top: (STRIP_H - 26) / 2, letterSpacing: "0.04em" }}
    >
      ×{n}
    </span>
  );
}

function SideboardCard({ card, deckSet }: { card: DeckCard; deckSet: string | null }) {
  const [failed, setFailed] = useState(false);
  const set = card.set ?? deckSet;
  const src = set && card.cn ? scryfallImageUrl(set, card.cn) : null;
  const count = card.count ?? 1;
  return (
    <div className="relative shrink-0 overflow-hidden rounded-[5px]" style={{ width: 94 }}>
      {src && !failed ? (
        <img
          src={src}
          alt={card.name}
          loading="lazy"
          onError={() => setFailed(true)}
          className="block w-full h-auto"
          draggable={false}
        />
      ) : (
        <div className="w-full aspect-[488/680] bg-surface2 border border-border flex items-start p-1.5">
          <span className="font-body text-subtle leading-tight" style={{ fontSize: 10 }}>{card.name}</span>
        </div>
      )}
      {count > 1 && <CountBadge n={count} />}
    </div>
  );
}
