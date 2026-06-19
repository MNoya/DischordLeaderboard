import { useEffect } from "react";
import { createPortal } from "react-dom";
import { ManaCost } from "../ManaPips";
import { CardImagePreview } from "./CardImagePreview";
import type { Card, P0P1PickStat } from "../../types/p0p1";

export function TiedCardsModal({
  label,
  stats,
  cardsByName,
  n,
  onClose,
}: {
  label: string;
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  n: number;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[360px] max-h-[80vh] overflow-y-auto themed-scrollbar rounded-xl border border-border2 bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border sticky top-0 bg-surface">
          <span className="font-display text-[14px] tracking-[0.08em] text-text">{label.toUpperCase()}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="ml-auto text-muted hover:text-text text-[20px] leading-none bg-transparent border-0 cursor-pointer p-1"
          >
            ×
          </button>
        </div>
        <div className="flex flex-col divide-y divide-border2">
          {stats.map((stat) => {
            const card = cardsByName.get(stat.cardName);
            return (
              <div key={stat.cardName} className="flex items-center gap-3 px-4 py-2.5">
                {card && (
                  <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-10 h-10 rounded overflow-hidden">
                    <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                  </CardImagePreview>
                )}
                <div className="flex-1 min-w-0 flex items-center gap-1.5">
                  <span className="text-text text-[13.5px] truncate">{stat.cardName}</span>
                  {card && <ManaCost cost={card.manaCost} size={12} />}
                </div>
                <span className="text-dim text-[13px] font-mono tabular-nums shrink-0">{stat.pickCount} picked</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>,
    document.body,
  );
}
