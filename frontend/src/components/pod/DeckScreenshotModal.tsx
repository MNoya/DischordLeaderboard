import { useEffect } from "react";
import { X } from "lucide-react";
import { Pips } from "../ManaPips";
import type { PodParticipant } from "../../data/fixtures/pod-sos-3";

interface Props {
  participant: PodParticipant;
  onClose: () => void;
}

export function DeckScreenshotModal({ participant, onClose }: Props) {
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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fadeIn px-4 py-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${participant.displayName}'s deck`}
    >
      <div
        className="relative bg-surface border border-border max-w-[920px] w-full max-h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-4 px-5 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <Pips colors={participant.deckColors} size={14} />
            <span
              className="font-display text-text leading-none truncate"
              style={{ fontSize: 22, letterSpacing: "0.04em", fontFamily: "'Bebas Neue', sans-serif" }}
            >
              {participant.displayName}
            </span>
            <span
              className="font-display text-muted tracking-[0.18em] uppercase"
              style={{ fontSize: 10 }}
            >
              Deck
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer"
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
          {participant.deckScreenshotCaption && (
            <div className="px-5 py-4 text-muted text-[13px] font-body border-t border-border">
              {participant.deckScreenshotCaption}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
