import { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { ManaCost } from "../ManaPips";
import { SectionLabel } from "../SectionLabel";
import { SlotPip, SLOT_ACCENT } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { groupBySlot, participantCount } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotDefinition } from "../../types/p0p1";

export function FullBreakdownList({
  pickStats,
  cardsByName,
  picksBySlot,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  picksBySlot?: Map<string, string>;
}) {
  const bySlot = useMemo(() => {
    const grouped = groupBySlot(pickStats);
    return new Map(
      SLOTS.map((slot) => [
        slot.key,
        [...(grouped.get(slot.key) ?? [])].sort((a, b) => b.pickCount - a.pickCount),
      ]),
    );
  }, [pickStats]);
  const entryCount = useMemo(() => participantCount(pickStats), [pickStats]);

  return (
    <div className="flex flex-col gap-1.5 lg:gap-3">
      <div className="relative flex items-center justify-center">
        <SectionLabel size={22} className="text-white">FULL BREAKDOWN</SectionLabel>
        <span className="absolute right-0 text-subtle text-[14px]">{entryCount} player{entryCount !== 1 ? "s" : ""}</span>
      </div>

      <div className="hidden lg:grid grid-cols-2 xl:grid-cols-3 gap-3 items-start">
        {SLOTS.map((slot) => (
          <SlotBreakdownPanel
            key={slot.key}
            slot={slot}
            rows={bySlot.get(slot.key) ?? []}
            cardsByName={cardsByName}
            yourPick={picksBySlot?.get(slot.key)}
          />
        ))}
      </div>

      <div className="lg:hidden flex flex-col gap-2">
        {SLOTS.map((slot) => (
          <SlotBreakdownPanel
            key={slot.key}
            slot={slot}
            rows={bySlot.get(slot.key) ?? []}
            cardsByName={cardsByName}
            yourPick={picksBySlot?.get(slot.key)}
            collapsible
          />
        ))}
      </div>
    </div>
  );
}

function SlotBreakdownPanel({
  slot,
  rows,
  cardsByName,
  yourPick,
  collapsible = false,
}: {
  slot: SlotDefinition;
  rows: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  yourPick?: string;
  collapsible?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const accent = SLOT_ACCENT[slot.key];
  const topPct = rows.length ? rows[0].pickPct : 0;
  const showRows = !collapsible || expanded;

  const header = (
    <div className="flex-1 flex items-center gap-2 px-3 py-2.5 min-w-0">
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
      <div className="absolute inset-y-0 left-0 z-10 w-1 pointer-events-none" style={{ background: accent }} />
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
          {rows.map((stat, i) => (
            <SlotRow
              key={stat.cardName}
              rank={i + 1}
              stat={stat}
              topPct={topPct}
              card={cardsByName.get(stat.cardName)}
              isYours={stat.cardName === yourPick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SlotRow({
  rank,
  stat,
  topPct,
  card,
  isYours,
}: {
  rank: number;
  stat: P0P1PickStat;
  topPct: number;
  card?: Card;
  isYours: boolean;
}) {
  const fillPct = topPct > 0 ? Math.max((stat.pickPct / topPct) * 100, 3) : 0;
  const isLeader = rank === 1;

  return (
    <div className="relative overflow-hidden border-b border-border2 last:border-b-0">
      <div className="absolute inset-y-0 left-0 bg-subtle/[0.08]" style={{ width: `${fillPct}%` }} />

      <div className={`relative flex items-center gap-2.5 pl-1.5 pr-3 py-1.5 ${isYours ? "bg-green/[0.07]" : ""}`}>
        <span className={`w-4 shrink-0 text-right font-mono tabular-nums text-[13px] ${isLeader ? "text-text font-bold" : "text-muted"}`}>
          {rank}
        </span>

        {card ? (
          <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-11 h-11 rounded-sm overflow-hidden shrink-0">
            <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
          </CardImagePreview>
        ) : (
          <div className="w-11 h-11 rounded-sm bg-surface2 shrink-0" />
        )}

        <div className="flex-1 min-w-0 flex items-center gap-2">
          <span className="text-text text-[15px] leading-snug line-clamp-2 min-w-0">{stat.cardName}</span>
          {isYours && (
            <span className="shrink-0 inline-block font-display tracking-[0.14em] uppercase text-[12.5px] leading-none px-2 py-1 bg-green text-bg">
              YOURS
            </span>
          )}
          <span className="ml-auto flex items-center gap-3 shrink-0">
            {card && <ManaCost cost={card.manaCost} size={12} />}
            <span className="font-mono tabular-nums text-[16px] font-semibold text-text w-8 text-right">
              {stat.pickCount}
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}
