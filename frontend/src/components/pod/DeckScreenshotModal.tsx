import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { X, ZoomIn, ZoomOut } from "lucide-react";
import { ArrowRight } from "../Brand";
import { ChamferedButton } from "../ChamferedButton";
import { Pips } from "../ManaPips";
import { Record } from "../Record";
import { useIsMobile } from "../../lib/use-is-mobile";
import {
  isDiscordCdnUrl,
  isDiscordUrlFresh,
  refreshDeckUrl,
} from "../../data/refresh-deck-url";

export const BREAKDOWN_CAPTION = "Seats, logs & replays";

export interface DeckLike {
  eventId?: string;
  displayName: string;
  participantDisplayName?: string;
  deckColors: string | null;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption?: string | null;
  record?: string | null;
}

interface Props {
  participant: DeckLike;
  breakdownHref?: string;
  onClose: () => void;
}

export function DeckScreenshotModal({ participant, breakdownHref, onClose }: Props) {
  const isMobile = useIsMobile();
  const [zoomed, setZoomed] = useState(false);
  const scrollerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

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
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [onClose]);

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fadeIn px-4 py-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${participant.displayName}'s deck`}
    >
      <div
        className="relative bg-surface border border-border max-w-[1400px] w-full max-h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center gap-3 lg:gap-6 px-5 py-3 border-b border-border shrink-0">
          <Pips colors={participant.deckColors ?? ""} size={14} />
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
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="lg:ml-auto text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer shrink-0"
          >
            <X size={18} />
          </button>
        </header>

        <div
          ref={scrollerRef}
          className={`flex-1 min-h-0 themed-scrollbar ${
            zoomed ? "overflow-auto" : "overflow-y-auto overflow-x-hidden"
          }`}
        >
          {showSkeleton ? (
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
        {isMobile && resolvedUrl && !showSkeleton && !imgFailed && (
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
                    VIEW BREAKDOWN
                    <ArrowRight size={12} />
                  </span>
                </ChamferedButton>
              </div>
            </div>
          </Link>
        ) : participant.deckScreenshotCaption ? (
          <div className="px-5 py-4 text-muted text-[13px] font-body italic border-t border-border shrink-0 bg-surface">
            {participant.deckScreenshotCaption}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}
