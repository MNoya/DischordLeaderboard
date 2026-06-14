import { useEffect, useMemo, useRef, useState } from "react";
import type { Card, SlotDefinition } from "../../types/p0p1";

interface Props {
  slot: SlotDefinition;
  cards: Card[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
}

export function CardSelectionGrid({
  slot,
  cards,
  pickedCards,
  onSelect,
}: Props) {
  const [search, setSearch] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

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
      <header className="flex items-center gap-3 mb-3">
        <span className="font-display text-text text-[18px] tracking-[0.1em] shrink-0">
          {slot.label}
        </span>
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search..."
          className="ml-auto w-60 bg-surface border border-border2 px-2.5 py-1.5 text-text text-[13px] placeholder:text-dim outline-none focus:border-green transition-colors"
        />
      </header>

      {filtered.length === 0 ? (
        <div className="py-8 text-center text-muted text-[14px]">
          No matching cards
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
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
