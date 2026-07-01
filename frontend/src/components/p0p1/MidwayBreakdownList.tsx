import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { ManaCost } from "../ManaPips";
import { SectionLabel } from "../SectionLabel";
import { SlotPip, breakdownStripAccent } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { SLOTS } from "../../data/p0p1Slots";
import { GIH_SAMPLE_FLOOR } from "../../data/p0p1Results";
import type { CardRating } from "../../data/p0p1Results";
import type { Card, P0P1PickStat, SlotDefinition, SlotKey } from "../../types/p0p1";

interface SlotRow {
  card: Card;
  gihwr: number | null;
  isYours: boolean;
}

export function MidwayBreakdownList({
  cards,
  cardsByName,
  ratingsByName,
  yourCardBySlot,
  crowdCardBySlot,
  pickStats,
}: {
  cards: Card[];
  cardsByName: Map<string, Card>;
  ratingsByName: Map<string, CardRating>;
  yourCardBySlot: Map<SlotKey, string>;
  crowdCardBySlot: Map<SlotKey, string>;
  pickStats: P0P1PickStat[];
}) {
  const pickedBySlot = useMemo(() => {
    const map = new Map<SlotKey, Set<string>>();
    for (const stat of pickStats) {
      const set = map.get(stat.slot) ?? new Set<string>();
      set.add(stat.cardName);
      map.set(stat.slot, set);
    }
    return map;
  }, [pickStats]);

  const bySlot = useMemo(() => {
    const empty = new Set<string>();
    return new Map(
      SLOTS.map((slot) => {
        const picked = pickedBySlot.get(slot.key) ?? new Set<string>();
        const eligible = cards.filter((c) => slot.filter(c, empty) && picked.has(c.name));
        const rows: SlotRow[] = eligible.map((c) => {
          const r = ratingsByName.get(c.name);
          const gihwr = r && r.gih >= GIH_SAMPLE_FLOOR && r.gihwr !== null ? r.gihwr : null;
          return {
            card: c,
            gihwr,
            isYours: yourCardBySlot.get(slot.key) === c.name,
          };
        });
        rows.sort((a, b) => {
          if (a.gihwr !== null && b.gihwr !== null) return b.gihwr - a.gihwr;
          if (a.gihwr !== null) return -1;
          if (b.gihwr !== null) return 1;
          return 0;
        });
        return [slot.key, rows] as const;
      }),
    );
  }, [cards, ratingsByName, yourCardBySlot, crowdCardBySlot, pickedBySlot]);

  return (
    <div className="flex flex-col gap-1.5 lg:gap-3">
      <div className="flex justify-center">
        <SectionLabel size={22} className="text-white">GIHWR BREAKDOWN</SectionLabel>
      </div>

      <div className="hidden lg:grid grid-cols-2 xl:grid-cols-3 gap-3 items-start">
        {SLOTS.map((slot) => (
          <SlotPanel
            key={slot.key}
            slot={slot}
            rows={bySlot.get(slot.key) ?? []}
            cardsByName={cardsByName}
          />
        ))}
      </div>

      <div className="lg:hidden flex flex-col gap-2">
        {SLOTS.map((slot) => (
          <SlotPanel
            key={slot.key}
            slot={slot}
            rows={bySlot.get(slot.key) ?? []}
            cardsByName={cardsByName}
            collapsible
          />
        ))}
      </div>
    </div>
  );
}

function SlotPanel({
  slot,
  rows,
  collapsible = false,
}: {
  slot: SlotDefinition;
  rows: SlotRow[];
  collapsible?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const accent = breakdownStripAccent(slot.key);
  const showRows = !collapsible || expanded;
  const wide = slot.key === "wildcard_uncommon";
  const topGihwr = rows.find((r) => r.gihwr !== null)?.gihwr ?? 0;

  const header = (
    <div className={`flex-1 flex items-center gap-2 ${wide ? "pl-4 pr-3" : "px-3"} py-2.5 min-w-0`}>
      <SlotPip slotKey={slot.key} size={20} />
      <span className="font-display text-[15px] tracking-[0.1em] text-white truncate">
        {slot.label.toUpperCase()}
      </span>
      <span className="ml-auto shrink-0 text-muted text-[12px] tabular-nums">
        {rows.length} card{rows.length !== 1 ? "s" : ""} chosen
      </span>
      {collapsible && (
        <ChevronDown
          size={16}
          className={`shrink-0 text-muted transition-transform duration-150 ${expanded ? "rotate-180" : ""}`}
        />
      )}
    </div>
  );

  return (
    <div className="relative border-y border-r border-border2 bg-surface overflow-hidden flex flex-col">
      <div className={`absolute inset-y-0 left-0 z-10 ${wide ? "w-2" : "w-1"} pointer-events-none`} style={{ background: accent }} />
      {collapsible ? (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className={`flex items-stretch bg-surface2 text-left cursor-pointer ${showRows ? "border-b border-border2" : ""}`}
        >
          {header}
        </button>
      ) : (
        <div className="flex items-stretch bg-surface2 border-b border-border2">{header}</div>
      )}

      {showRows && (
        <div>
          {rows.map((row, i) => (
            <GihwrRow
              key={row.card.name}
              rank={i + 1}
              row={row}
              topGihwr={topGihwr}
              wide={wide}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function GihwrRow({
  rank,
  row,
  topGihwr,
  wide,
}: {
  rank: number;
  row: SlotRow;
  topGihwr: number;
  wide: boolean;
}) {
  const fillPct =
    row.gihwr !== null && topGihwr > 0
      ? Math.max(((row.gihwr - 0.45) / (0.70 - 0.45)) * 100, 3)
      : 0;
  const isLeader = rank === 1;
  const highlight = row.isYours ? "bg-green/[0.07]" : "";

  return (
    <div className="relative overflow-hidden border-b border-border2 last:border-b-0">
      {row.gihwr !== null && (
        <div className="absolute inset-y-0 left-0 bg-subtle/[0.07]" style={{ width: `${fillPct}%` }} />
      )}

      <div className={`relative flex items-center gap-2.5 ${wide ? "pl-4" : "pl-1.5"} pr-3 py-1.5 ${highlight}`}>
        <span className={`w-4 shrink-0 text-right font-mono tabular-nums text-[13px] ${isLeader ? "text-text font-bold" : "text-muted"}`}>
          {rank}
        </span>

        <CardImagePreview imageUrl={row.card.imageNormal} alt={row.card.name} className="w-11 h-11 rounded-sm overflow-hidden shrink-0">
          <img src={row.card.imageArtCrop} alt={row.card.name} className="w-full h-full object-cover" />
        </CardImagePreview>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-text text-[15px] leading-snug line-clamp-2 min-w-0">{row.card.name}</span>
            {row.isYours && (
              <span className="shrink-0 inline-block font-display tracking-[0.14em] uppercase text-[12.5px] leading-none px-2 py-1 bg-green text-bg">
                YOURS
              </span>
            )}
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3 shrink-0">
          <ManaCost cost={row.card.manaCost} size={12} />
          <div className={`font-mono tabular-nums text-[13px] font-semibold ${row.gihwr !== null ? "text-text" : "text-muted"}`}>
            {row.gihwr !== null ? `${(row.gihwr * 100).toFixed(1)}%` : "—"}
          </div>
        </div>
      </div>
    </div>
  );
}
