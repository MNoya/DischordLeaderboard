import { useEffect, useMemo, useRef, useState } from "react";
import type { MshCard, SlotDefinition } from "../../types/p0p1";

interface Props {
  slot: SlotDefinition;
  cards: MshCard[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
  onCancel: () => void;
}

export function CardSelectionGrid({
  slot,
  cards,
  pickedCards,
  onSelect,
  onCancel,
}: Props) {
  const [search, setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const eligible = useMemo(
    () => cards.filter((c) => slot.filter(c, pickedCards)),
    [cards, slot, pickedCards],
  );

  const filtered = useMemo(() => {
    if (!search.trim()) return eligible;
    const q = search.toLowerCase();
    return eligible.filter((c) => c.name.toLowerCase().includes(q));
  }, [eligible, search]);

  return (
    <div className="animate-fadeIn">
      <header className="flex items-center justify-between mb-3">
        <span className="font-display text-text text-[18px] tracking-[0.1em]">
          {slot.label}
        </span>
        <button
          type="button"
          onClick={onCancel}
          aria-label="Cancel"
          className="text-muted hover:text-text transition-colors p-1 bg-transparent border-0 cursor-pointer text-[20px] leading-none"
        >
          ×
        </button>
      </header>

      <input
        ref={inputRef}
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search cards..."
        className="w-full bg-surface border border-border2 px-3 py-2 text-text text-[14px] placeholder:text-dim outline-none focus:border-green transition-colors mb-3"
      />

      {filtered.length === 0 ? (
        <div className="py-8 text-center text-muted text-[14px]">
          No matching cards
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {filtered.map((card) => (
            <button
              type="button"
              key={card.name}
              onClick={() => onSelect(card.name)}
              className="bg-transparent border-2 border-transparent hover:border-green transition-colors cursor-pointer p-0 rounded-lg overflow-hidden"
            >
              <img
                src={card.imageNormal}
                alt={card.name}
                className="w-full block"
                style={{ aspectRatio: "488 / 680" }}
                loading="lazy"
              />
            </button>
          ))}
        </div>
      )}

      <footer className="mt-3">
        <span className="text-muted text-[12px]">
          {filtered.length} card{filtered.length !== 1 ? "s" : ""} available
        </span>
      </footer>
    </div>
  );
}
