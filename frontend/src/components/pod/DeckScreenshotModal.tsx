import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { ArrowRight } from "../Brand";
import { ChamferedButton } from "../ChamferedButton";
import { Pips } from "../ManaPips";
import { Record } from "../Record";

export const BREAKDOWN_CAPTION = "Seats, logs & replays";

export interface DeckLike {
  displayName: string;
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

        <div className="flex-1 min-h-0 overflow-y-auto themed-scrollbar">
          {participant.deckScreenshotUrl ? (
            <img
              src={participant.deckScreenshotUrl}
              alt={`${participant.displayName} deck screenshot`}
              className="block w-full h-auto"
            />
          ) : (
            <div className="px-5 py-16 text-center text-muted font-body">
              No deck screenshot available
            </div>
          )}
        </div>

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
