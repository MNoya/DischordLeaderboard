import { useMemo, useState, type ReactNode } from "react";
import { ManaCost } from "../ManaPips";
import { SectionLabel } from "../SectionLabel";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { globalRanked, participantCount } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotKey } from "../../types/p0p1";

export function FullBreakdownList({
  pickStats,
  cardsByName,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  const [filter, setFilter] = useState<SlotKey | "all">("all");
  const ranked = useMemo(() => globalRanked(pickStats), [pickStats]);
  const rows = filter === "all" ? ranked : ranked.filter((s) => s.slot === filter);
  const slotLabels = useMemo(() => new Map(SLOTS.map((s) => [s.key, s.label])), []);
  const n = participantCount(pickStats);

  return (
    <div className="flex flex-col gap-2">
      <SectionLabel size={16} className="mb-1">FULL BREAKDOWN</SectionLabel>
      <div className="flex items-center gap-1.5 flex-wrap">
        <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
          All
        </FilterChip>
        {SLOTS.map((slot) => (
          <FilterChip key={slot.key} active={filter === slot.key} onClick={() => setFilter(slot.key)}>
            <SlotPip slotKey={slot.key} size={14} />
          </FilterChip>
        ))}
      </div>
      <div className="flex flex-col border border-border2 divide-y divide-border2 bg-surface">
        {rows.map((stat) => {
          const card = cardsByName.get(stat.cardName);
          return (
            <div key={`${stat.slot}-${stat.cardName}`} className="flex items-center gap-3 px-3 py-2">
              {card && (
                <CardImagePreview
                  imageUrl={card.imageNormal}
                  alt={card.name}
                  className="w-10 h-10 lg:w-12 lg:h-12 rounded overflow-hidden shrink-0"
                >
                  <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                </CardImagePreview>
              )}
              <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-text text-[13.5px] truncate">{stat.cardName}</span>
                  {card && <ManaCost cost={card.manaCost} size={12} />}
                </div>
                <div className="flex items-center gap-1 text-dim text-[11px]">
                  <SlotPip slotKey={stat.slot} size={11} />
                  <span className="truncate">{slotLabels.get(stat.slot)}</span>
                </div>
              </div>
              <span className="text-text text-[14px] font-mono tabular-nums shrink-0">
                {stat.pickCount} / {n}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FilterChip({
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
      onClick={onClick}
      className={`px-2.5 py-1.5 rounded-full border text-[12px] flex items-center gap-1 cursor-pointer transition-colors ${
        active ? "border-green/60 bg-green/10 text-green" : "border-border2 bg-surface text-dim hover:text-text"
      }`}
    >
      {children}
    </button>
  );
}
