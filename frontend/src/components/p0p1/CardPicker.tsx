import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { MshCard, SlotDefinition } from "../../types/p0p1";
import { ManaCost } from "../ManaPips";
import { CardImagePreview } from "./CardImagePreview";

interface Props {
  slot: SlotDefinition;
  cards: MshCard[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
  onClose: () => void;
}

export function CardPicker({
  slot,
  cards,
  pickedCards,
  onSelect,
  onClose,
}: Props) {
  const [search, setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const eligible = useMemo(
    () => cards.filter((c) => slot.filter(c, pickedCards)),
    [cards, slot, pickedCards],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return eligible;
    const q = search.toLowerCase();
    return eligible.filter((c) => c.name.toLowerCase().includes(q));
  }, [eligible, search]);

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-fadeIn px-4 py-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Pick a card for ${slot.label}`}
    >
      <div
        className="relative bg-bg border border-border w-full max-w-[560px] max-h-full flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
          <span className="font-display text-text text-[18px] tracking-[0.1em]">
            {slot.label}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer text-[20px] leading-none"
          >
            ×
          </button>
        </header>

        <div className="px-4 py-3 border-b border-border shrink-0">
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search cards..."
            className="w-full bg-surface border border-border2 px-3 py-2 text-text text-[14px] placeholder:text-dim outline-none focus:border-green transition-colors"
          />
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 themed-scrollbar">
          {filtered.length === 0 ? (
            <div className="px-5 py-8 text-center text-muted text-[14px]">
              No matching cards
            </div>
          ) : (
            <div className="flex flex-col">
              {filtered.map((card) => (
                <button
                  type="button"
                  onClick={() => onSelect(card.name)}
                  key={card.name}
                  className="flex items-center gap-3 px-4 py-2.5 border-0 border-b border-border hover:bg-surface transition-colors group"
                >
                  <CardImagePreview imageUrl={card.imageNormal} alt={card.name}>
                    <img
                      src={card.imageArtCrop}
                      alt=""
                      className="w-16 h-10 object-cover border border-border2"
                      loading="lazy"
                    />
                  </CardImagePreview>
                  <div className="flex-1 min-w-0 text-left bg-transparent border-0 cursor-pointer p-0">
                    <div className="flex items-center gap-2">
                      <div className="text-text text-[14px] truncate group-hover:text-green transition-colors">
                        {card.name}
                      </div>
                      <ManaCost cost={card.manaCost} />
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <footer className="px-4 py-2.5 border-t border-border shrink-0">
          <span className="text-muted text-[12px]">
            {filtered.length} card{filtered.length !== 1 ? "s" : ""} available
          </span>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
