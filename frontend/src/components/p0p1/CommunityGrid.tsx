import { useState } from "react";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { TiedCardsModal } from "./TiedCardsModal";
import { groupBySlot, findExtremes } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotKey } from "../../types/p0p1";

export function CommunityGrid({
  pickStats,
  cardsByName,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  const grouped = groupBySlot(pickStats);
  return (
    <div className="grid grid-cols-8 gap-2">
      {SLOTS.map((slot) => {
        const slotStats = grouped.get(slot.key) ?? [];
        const { most, least } = findExtremes(slotStats);
        return (
          <SlotColumn
            key={slot.key}
            slotKey={slot.key}
            label={slot.label}
            most={most}
            least={least}
            cardsByName={cardsByName}
          />
        );
      })}
    </div>
  );
}

function SlotColumn({
  slotKey,
  label,
  most,
  least,
  cardsByName,
}: {
  slotKey: SlotKey;
  label: string;
  most: P0P1PickStat[];
  least: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  return (
    <div className="flex flex-col border border-border2 bg-surface overflow-hidden min-w-0">
      <div className="flex items-center gap-1 px-1.5 py-1 bg-surface2 border-b border-border2 min-w-0">
        <SlotPip slotKey={slotKey} size={13} />
        <span className="text-dim text-[10px] tracking-[0.06em] truncate">{label}</span>
      </div>
      <PickHalf label="MOST PICKED" stats={most} cardsByName={cardsByName} tone="green" />
      <div className="h-px bg-border2 shrink-0" />
      <PickHalf label="LEAST PICKED" stats={least} cardsByName={cardsByName} tone="red" />
    </div>
  );
}

function PickHalf({
  label,
  stats,
  cardsByName,
  tone,
}: {
  label: string;
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  tone: "green" | "red";
}) {
  const [modalOpen, setModalOpen] = useState(false);
  if (stats.length === 0) {
    return <div className="aspect-square bg-surface2" />;
  }
  const tied = stats.length > 1;
  const shown = stats.slice(0, 4);
  const pct = stats[0].pickPct;

  return (
    <div className="relative aspect-square group">
      {tied ? (
        <div className="grid grid-cols-2 grid-rows-2 gap-px h-full w-full bg-border2">
          {shown.map((stat) => {
            const card = cardsByName.get(stat.cardName);
            return card ? (
              <CardImagePreview key={stat.cardName} imageUrl={card.imageNormal} alt={card.name} className="overflow-hidden">
                <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
              </CardImagePreview>
            ) : (
              <div key={stat.cardName} className="bg-surface2" />
            );
          })}
          {Array.from({ length: Math.max(0, 4 - shown.length) }, (_, i) => (
            <div key={`blank-${i}`} className="bg-surface2" />
          ))}
        </div>
      ) : (
        (() => {
          const card = cardsByName.get(stats[0].cardName);
          return card ? (
            <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-full h-full">
              <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
            </CardImagePreview>
          ) : (
            <div className="w-full h-full bg-surface2" />
          );
        })()
      )}

      <div className="absolute top-0 left-0 right-0 px-1.5 py-1 bg-gradient-to-b from-black/70 to-transparent flex items-center justify-between gap-1 pointer-events-none">
        <span className={`text-[10px] tracking-[0.08em] font-display ${tone === "green" ? "text-green" : "text-red"}`}>
          {label}
        </span>
        {tied && (
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="text-[10px] font-mono px-1 py-0.5 rounded bg-black/60 text-white border border-white/20 cursor-pointer shrink-0 pointer-events-auto"
          >
            {stats.length > 4 ? `+${stats.length}` : `${stats.length}-way`}
          </button>
        )}
      </div>

      <div className="absolute bottom-0 left-0 right-0 px-1.5 py-1 bg-gradient-to-t from-black/70 to-transparent pointer-events-none">
        <span className="text-white text-[12px] font-mono tabular-nums">{pct}%</span>
      </div>

      {modalOpen && (
        <TiedCardsModal
          label={label}
          stats={stats}
          cardsByName={cardsByName}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}
