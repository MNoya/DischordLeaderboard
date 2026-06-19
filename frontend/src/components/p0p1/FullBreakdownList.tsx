import { useMemo, useState, type ReactNode } from "react";
import { ManaCost } from "../ManaPips";
import { SectionLabel } from "../SectionLabel";
import { SlotPip, SLOT_ACCENT } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { globalRanked } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotKey } from "../../types/p0p1";

const DESKTOP_COLS = "28px 36px 2fr 160px 0.5fr 50px";
const MOBILE_COLS = "18px 28px 1fr 40px";

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
  const maxCount = rows.length > 0 ? Math.max(...rows.map((s) => s.pickCount)) : 0;

  return (
    <div className="flex flex-col gap-2">
      <SectionLabel size={16} className="mb-1 text-white">FULL BREAKDOWN</SectionLabel>
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

      <div className="hidden lg:block border border-border2 bg-surface">
        <div
          className="grid text-dim text-[10px] tracking-[0.08em] font-display px-3 py-1.5 border-b border-border2"
          style={{ gridTemplateColumns: DESKTOP_COLS }}
        >
          <span>#</span>
          <span />
          <span>CARD</span>
          <span>SLOT</span>
          <span>SHARE</span>
          <span className="text-right">PICKED</span>
        </div>
        {rows.map((stat, i) => {
          const card = cardsByName.get(stat.cardName);
          return (
            <div
              key={`${stat.slot}-${stat.cardName}`}
              className={`grid items-center px-3 py-1.5 ${i % 2 === 1 ? "bg-surface2/40" : ""}`}
              style={{ gridTemplateColumns: DESKTOP_COLS }}
            >
              <span className="text-dim text-[11px] font-mono">{i + 1}</span>
              {card ? (
                <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-7 h-7 rounded overflow-hidden">
                  <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                </CardImagePreview>
              ) : (
                <div className="w-7 h-7 rounded bg-surface2" />
              )}
              <div className="flex items-center gap-1.5 min-w-0 pr-2">
                <span className="text-text text-[12.5px] truncate">{stat.cardName}</span>
                {card && <ManaCost cost={card.manaCost} size={11} />}
              </div>
              <span className="text-dim text-[11px] truncate pr-2">{slotLabels.get(stat.slot)}</span>
              <div className="h-1.5 bg-surface2 rounded-sm overflow-hidden">
                <div
                  className="h-full rounded-sm"
                  style={{
                    width: `${maxCount > 0 ? Math.round((stat.pickCount / maxCount) * 100) : 0}%`,
                    background: SLOT_ACCENT[stat.slot],
                  }}
                />
              </div>
              <span className="text-text text-[12.5px] font-mono tabular-nums text-right">{stat.pickCount}</span>
            </div>
          );
        })}
      </div>

      <div className="lg:hidden border border-border2 bg-surface">
        <div
          className="grid text-dim text-[9px] tracking-[0.08em] font-display px-2.5 py-1.5 border-b border-border2"
          style={{ gridTemplateColumns: MOBILE_COLS }}
        >
          <span />
          <span />
          <span>CARD</span>
          <span className="text-right">PICKED</span>
        </div>
        {rows.map((stat, i) => {
          const card = cardsByName.get(stat.cardName);
          return (
            <div
              key={`${stat.slot}-${stat.cardName}`}
              className={`grid items-center px-2.5 py-1.5 ${i % 2 === 1 ? "bg-surface2/40" : ""}`}
              style={{ gridTemplateColumns: MOBILE_COLS }}
            >
              <span className="text-dim text-[10px] font-mono">{i + 1}</span>
              {card ? (
                <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-6 h-6 rounded overflow-hidden">
                  <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                </CardImagePreview>
              ) : (
                <div className="w-6 h-6 rounded bg-surface2" />
              )}
              <div className="min-w-0 pr-1">
                <div className="flex items-center justify-between gap-1 min-w-0">
                  <span className="text-text text-[12px] truncate">{stat.cardName}</span>
                  {card && <ManaCost cost={card.manaCost} size={10} />}
                </div>
                <div className="text-dim text-[9.5px] truncate">{slotLabels.get(stat.slot)}</div>
              </div>
              <span className="text-text text-[12px] font-mono tabular-nums text-right">{stat.pickCount}</span>
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
