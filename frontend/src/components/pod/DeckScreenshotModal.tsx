import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, X, ZoomIn, ZoomOut } from "lucide-react";
import { ArrowRight, GiRoundTable } from "../Icons";
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
  const [zoomed, setZoomed] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  const hasScreenshot = participant.deckScreenshotUrl !== null;
  const hasDecklist = (participant.mainboard?.cards.length ?? 0) > 0;
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

  useEffect(() => {
    setZoomed(false);
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

  const toggleZoom = () => {
    if (!isMobile) return;
    setZoomed((prev) => {
      const next = !prev;
      requestAnimationFrame(() => {
        const scroller = scrollerRef.current;
        const img = imgRef.current;
        if (next && scroller && img) {
          const target = Math.max(0, (img.scrollWidth - scroller.clientWidth) / 2);
          scroller.scrollLeft = target;
        } else if (!next && scroller) {
          scroller.scrollLeft = 0;
        }
      });
      return next;
    });
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center gap-1 md:gap-2 bg-black/80 backdrop-blur-sm animate-fadeIn px-2 md:px-4 py-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${participant.displayName}'s deck`}
    >
      {onPrev && <NavButton side="left" onClick={onPrev} />}
      <div
        className="relative bg-surface border border-border flex-1 max-w-[1400px] max-h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 lg:gap-6 pl-9 pr-5 py-3 border-b border-border shrink-0">
          <Pips colors={participant.deckColors ?? ""} size={18} />
          <span
            className="font-display text-text truncate flex-1 text-center lg:text-left lg:flex-initial"
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
          {hasScreenshot && hasDecklist && (
            <div className="flex shrink-0 border border-border lg:ml-auto" role="tablist">
              <TabButton active={effectiveTab === "screenshot"} onClick={() => setTab("screenshot")}>
                IMAGE
              </TabButton>
              <TabButton active={effectiveTab === "decklist"} onClick={() => setTab("decklist")}>
                CARD POOL
              </TabButton>
            </div>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className={cn(
              "text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer shrink-0",
              !(hasScreenshot && hasDecklist) && "lg:ml-auto",
            )}
          >
            <X size={18} />
          </button>
        </header>

        <div
          ref={scrollerRef}
          className={`flex-1 min-h-0 themed-scrollbar ${
            effectiveTab === "decklist" || !zoomed ? "overflow-y-auto overflow-x-hidden" : "overflow-auto"
          }`}
        >
          {effectiveTab === "decklist" && participant.mainboard ? (
            <DecklistView mainboard={participant.mainboard} />
          ) : showSkeleton ? (
            <div className="w-full aspect-[5/2] bg-surface2 animate-pulse" />
          ) : imgFailed ? (
            <div className="px-5 py-16 text-center text-muted font-body">
              Deck screenshot failed to load
            </div>
          ) : resolvedUrl ? (
            <img
              ref={imgRef}
              src={resolvedUrl}
              alt={`${participant.displayName} deck screenshot`}
              onClick={toggleZoom}
              className={`block h-auto select-none ${
                zoomed ? "w-auto max-w-none" : "w-full"
              } ${isMobile ? (zoomed ? "cursor-zoom-out" : "cursor-zoom-in") : ""}`}
              draggable={false}
            />
          ) : (
            <div className="px-5 py-16 text-center text-muted font-body">
              No deck screenshot available
            </div>
          )}
        </div>
        {effectiveTab === "screenshot" && isMobile && resolvedUrl && !showSkeleton && !imgFailed && (
          <button
            type="button"
            onClick={toggleZoom}
            aria-label={zoomed ? "Exit zoom" : "Zoom deck"}
            className="absolute right-2 z-10 inline-flex items-center gap-1.5 bg-bg/85 border border-border text-text px-2.5 py-1.5 font-display tracking-[0.14em] text-[11px] cursor-pointer backdrop-blur-sm"
            style={{ top: 60 }}
          >
            {zoomed ? <ZoomOut size={13} /> : <ZoomIn size={13} />}
            {zoomed ? "FIT" : "ZOOM"}
          </button>
        )}

        {breakdownHref ? (
          <Link to={breakdownHref} className="block no-underline border-t border-border shrink-0">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2 md:gap-4 px-3 md:px-4 py-3 bg-surface hover:bg-green/5 transition-colors cursor-pointer">
              {participant.deckScreenshotCaption ? (
                <span className="text-muted text-[15px] font-body italic leading-snug min-w-0 text-center md:text-left md:truncate md:pr-1 md:pl-5 md:leading-none">
                  {participant.deckScreenshotCaption}
                </span>
              ) : (
                <span className="hidden md:block md:pl-5" />
              )}
              <div className="flex items-center justify-end gap-4 shrink-0 self-end md:self-auto">
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
        ) : participant.deckScreenshotCaption ? (
          <div className="pl-9 pr-5 py-4 text-muted text-[15px] font-body italic leading-snug border-t border-border shrink-0 bg-surface">
            {participant.deckScreenshotCaption}
          </div>
        ) : null}
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
      {onNext && <NavButton side="right" onClick={onNext} />}
    </div>,
    document.body,
  );
}

function NavButton({ side, onClick }: { side: "left" | "right"; onClick: () => void }) {
  const Chevron = side === "left" ? ChevronLeft : ChevronRight;
  const label = side === "left" ? "PREV" : "NEXT";
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      aria-label={side === "left" ? "Previous deck" : "Next deck"}
      className="shrink-0 inline-flex items-center gap-1 p-1.5 cursor-pointer bg-transparent border-0 text-green/80 hover:text-green transition-colors font-display tracking-[0.18em] text-[15px]"
    >
      {side === "left" && <Chevron size={34} strokeWidth={2.5} />}
      <span className="hidden min-[1600px]:inline">{label}</span>
      {side === "right" && <Chevron size={34} strokeWidth={2.5} />}
    </button>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "font-display tracking-[0.16em] px-6 py-2.5 cursor-pointer transition-colors leading-none",
        "outline-none focus:outline-none focus-visible:outline-none",
        active ? "bg-green/15 text-green" : "bg-transparent text-muted hover:text-text",
      )}
      style={{ fontSize: 19 }}
    >
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
    <div className="px-4 md:px-5 py-5 overflow-x-auto themed-scrollbar">
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
