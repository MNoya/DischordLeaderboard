import { useMemo, useState } from "react";
import { ManaCost } from "../ManaPips";
import { SectionLabel } from "../SectionLabel";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { groupBySlot, findExtremes, classifyYourPick } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotDefinition } from "../../types/p0p1";

export function FullBreakdownList({
  pickStats,
  cardsByName,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
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

  return (
    <div className="flex flex-col gap-2">
      <SectionLabel size={16} className="mb-1 text-white">FULL BREAKDOWN</SectionLabel>

      <div className="hidden lg:grid grid-cols-4 gap-3 items-start">
        {SLOTS.map((slot) => (
          <SlotPanel key={slot.key} slot={slot} rows={bySlot.get(slot.key) ?? []} cardsByName={cardsByName} />
        ))}
      </div>

      <div className="lg:hidden border border-border2 bg-surface divide-y divide-border2">
        {SLOTS.map((slot) => (
          <SlotAccordionSection key={slot.key} slot={slot} rows={bySlot.get(slot.key) ?? []} cardsByName={cardsByName} />
        ))}
      </div>
    </div>
  );
}

function SlotPanel({
  slot,
  rows,
  cardsByName,
}: {
  slot: SlotDefinition;
  rows: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  const { most } = findExtremes(rows);

  return (
    <div className="border border-border2 bg-surface overflow-hidden flex flex-col">
      <div className="px-2.5 py-2 bg-surface2 border-b border-border2 flex items-center gap-2">
        <SlotPip slotKey={slot.key} size={14} />
        <span className="text-subtle text-[11px] tracking-[0.06em] font-display truncate">{slot.label.toUpperCase()}</span>
        <span className="ml-auto text-dim text-[10px] font-mono shrink-0">{rows.length} cards</span>
      </div>
      <div className="divide-y divide-border2">
        {rows.map((stat, i) => {
          const card = cardsByName.get(stat.cardName);
          const classification = classifyYourPick(stat, most, []);
          return (
            <div key={stat.cardName} className="flex items-center gap-2 px-2.5 py-1.5">
              <span className="text-dim text-[10px] font-mono w-3 shrink-0">{i + 1}</span>
              {card ? (
                <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-7 h-7 rounded overflow-hidden shrink-0">
                  <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                </CardImagePreview>
              ) : (
                <div className="w-7 h-7 rounded bg-surface2 shrink-0" />
              )}
              <div className="flex-1 min-w-0 flex items-center gap-1.5">
                <span className="text-text text-[12px] truncate">{stat.cardName}</span>
                {classification.qualifier && (
                  <span className="text-[8px] font-display tracking-wide text-cyan border border-cyan/50 rounded-sm px-1 shrink-0">
                    {classification.qualifier}
                  </span>
                )}
              </div>
              {card && <ManaCost cost={card.manaCost} size={10} />}
              <span className="text-subtle text-[11.5px] font-mono tabular-nums w-5 text-right shrink-0">{stat.pickCount}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SlotAccordionSection({
  slot,
  rows,
  cardsByName,
}: {
  slot: SlotDefinition;
  rows: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  const [expanded, setExpanded] = useState(false);
  const { most } = findExtremes(rows);
  const top = rows[0];
  const tiedAtTop = top ? rows.filter((r) => r.pickCount === top.pickCount).length : 0;
  const teaser = top
    ? tiedAtTop > 1
      ? `${tiedAtTop}-way tie at top · ${top.pickCount} each`
      : `Top: ${top.cardName} · ${top.pickCount} picked`
    : "No picks yet";

  return (
    <div>
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center gap-2 px-2.5 py-2.5 text-left cursor-pointer"
      >
        <SlotPip slotKey={slot.key} size={16} />
        <div className="min-w-0 flex-1">
          <span className="font-display text-[11px] tracking-[0.06em] text-subtle">{slot.label.toUpperCase()}</span>
          {!expanded && (
            <div className="text-dim text-[10px] truncate mt-0.5">{teaser} · {rows.length} cards</div>
          )}
        </div>
        <span className="text-dim text-[10px] shrink-0">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && (
        <div className="border-t border-border2">
          {rows.map((stat, i) => {
            const card = cardsByName.get(stat.cardName);
            const classification = classifyYourPick(stat, most, []);
            return (
              <div
                key={stat.cardName}
                className="flex items-center gap-2.5 px-2.5 py-2 border-b border-border2 last:border-b-0"
              >
                <span className="text-dim text-[10px] w-4 text-right shrink-0">{i + 1}</span>
                {card ? (
                  <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-9 h-9 rounded-sm overflow-hidden shrink-0">
                    <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
                  </CardImagePreview>
                ) : (
                  <div className="w-9 h-9 rounded-sm bg-surface2 shrink-0" />
                )}
                <div className="min-w-0 flex-1 flex items-center gap-1">
                  <span className="text-text text-[12.5px] truncate min-w-0">{stat.cardName}</span>
                  {classification.qualifier && (
                    <span className="text-[7.5px] font-display tracking-wide text-cyan border border-cyan/50 rounded-sm px-1 shrink-0">
                      {classification.qualifier}
                    </span>
                  )}
                  {card && <span className="ml-auto shrink-0"><ManaCost cost={card.manaCost} size={10} /></span>}
                </div>
                <div className="font-mono tabular-nums text-[15px] font-semibold shrink-0 w-7 text-right">{stat.pickCount}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
