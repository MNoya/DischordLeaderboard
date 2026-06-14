import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";
import type { Card, SlotDefinition } from "../../types/p0p1";
import { Pip } from "../ManaPips";
import { SlotPip } from "./slotVisuals";

const WUBRG = ["W", "U", "B", "R", "G"] as const;
type Color = (typeof WUBRG)[number];

interface Props {
  slot: SlotDefinition;
  cards: Card[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
  selectedName?: string;
  minColW?: number;
  showLabel?: boolean;
}

export function CardSelectionGrid({
  slot,
  cards,
  pickedCards,
  onSelect,
  selectedName,
  minColW = 200,
  showLabel = true,
}: Props) {
  const [search, setSearch] = useState("");
  const [color, setColor] = useState<Color | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const isWildcard = slot.key === "wildcard_common" || slot.key === "wildcard_uncommon";

  const toggleColor = (c: Color) => setColor((prev) => (prev === c ? null : c));

  const eligible = useMemo(
    () => cards.filter((c) => slot.filter(c, pickedCards)),
    [cards, slot, pickedCards],
  );

  const filtered = useMemo(() => {
    let list = eligible;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((c) => c.name.toLowerCase().includes(q));
    }
    if (isWildcard && color) {
      list = list.filter((c) => c.colors.includes(color));
    }
    return list;
  }, [eligible, search, isWildcard, color]);

  const colorFilter = isWildcard ? (
    <div className="flex items-center gap-1">
      {WUBRG.map((c) => {
        const on = color === c;
        return (
          <button
            key={c}
            type="button"
            onClick={() => toggleColor(c)}
            aria-label={c}
            className={`flex items-center justify-center w-7 h-7 transition ${
              on ? "opacity-100" : "opacity-35 hover:opacity-100"
            }`}
          >
            <Pip c={c} size={17} />
          </button>
        );
      })}
    </div>
  ) : null;

  const searchBox = (
    <div className="relative ml-auto w-full max-w-[280px]">
      <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-dim pointer-events-none" />
      <input
        ref={inputRef}
        type="text"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search..."
        className="w-full bg-surface border border-border2 pl-8 pr-2.5 py-1.5 text-text text-[13px] placeholder:text-dim outline-none focus:border-green/60 transition-colors"
      />
    </div>
  );

  return (
    <div className="animate-fadeIn">
      {showLabel ? (
        <header className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 mb-3">
          <div className="flex items-center gap-2 min-w-0 pl-3">
            <SlotPip slotKey={slot.key} size={24} />
            <span className="font-display text-text text-[22px] tracking-[0.1em] truncate">{slot.label}</span>
          </div>
          <div className="flex justify-center">{colorFilter}</div>
          {searchBox}
        </header>
      ) : (
        <header className="flex items-center gap-2 mb-3">
          {colorFilter}
          {searchBox}
        </header>
      )}

      {filtered.length === 0 ? (
        <div className="py-8 text-center text-muted text-[14px]">
          No matching cards
        </div>
      ) : (
        <div className="grid gap-3.5" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${minColW}px, 1fr))` }}>
          {filtered.map((card) => {
            const selected = card.name === selectedName;
            return (
              <button
                type="button"
                key={card.name}
                onClick={() => onSelect(card.name)}
                className={`relative bg-transparent cursor-pointer p-0 rounded-[3%] overflow-hidden outline outline-1 -outline-offset-1 outline-white/10 transition-transform duration-150 hover:z-10 ${
                  selected ? "p0p1-card-selected z-10 scale-[1.03] hover:scale-[1.05]" : "hover:scale-[1.04]"
                }`}
              >
                <img
                  src={card.imageNormal}
                  alt={card.name}
                  className="w-full block"
                  style={{ aspectRatio: "488 / 680" }}
                  loading="lazy"
                />
              </button>
            );
          })}
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
