import { useState } from "react";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { TiedCardsModal } from "./TiedCardsModal";
import { SectionLabel } from "../SectionLabel";
import { groupBySlot, findExtremes, participantCount } from "../../data/p0p1Stats";
import { SLOTS } from "../../data/p0p1Slots";
import type { Card, P0P1PickStat, SlotKey } from "../../types/p0p1";

const MAX_MOSAIC = 4;

export function CommunityGrid({
  pickStats,
  cardsByName,
}: {
  pickStats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
}) {
  const grouped = groupBySlot(pickStats);
  const extremesBySlot = new Map(SLOTS.map((slot) => [slot.key, findExtremes(grouped.get(slot.key) ?? [])]));
  const n = participantCount(pickStats);

  return (
    <div className="flex flex-col gap-6">
      <PickRow
        title="MOST PICKED CARDS"
        tone="green"
        entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: extremesBySlot.get(slot.key)!.most }))}
        cardsByName={cardsByName}
        n={n}
      />
      <PickRow
        title="LEAST PICKED CARDS"
        tone="red"
        entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: extremesBySlot.get(slot.key)!.least }))}
        cardsByName={cardsByName}
        n={n}
      />
    </div>
  );
}

function PickRow({
  title,
  tone,
  entries,
  cardsByName,
  n,
}: {
  title: string;
  tone: "green" | "red";
  entries: { slotKey: SlotKey; label: string; stats: P0P1PickStat[] }[];
  cardsByName: Map<string, Card>;
  n: number;
}) {
  return (
    <div>
      <SectionLabel size={13} color={tone === "green" ? "#2ee85c" : "#ff5e5e"} className="mb-2">
        {title}
      </SectionLabel>
      <div className="grid grid-cols-8 gap-2">
        {entries.map(({ slotKey, label, stats }) => (
          <PickTile key={slotKey} slotKey={slotKey} label={label} stats={stats} tone={tone} cardsByName={cardsByName} n={n} />
        ))}
      </div>
    </div>
  );
}

function PickTile({
  slotKey,
  label,
  stats,
  tone,
  cardsByName,
  n,
}: {
  slotKey: SlotKey;
  label: string;
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  tone: "green" | "red";
  n: number;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const toneClass = tone === "green" ? "text-green" : "text-red";

  return (
    <div className="flex flex-col border border-border2 bg-surface overflow-hidden min-w-0">
      <div className="flex items-center gap-1 px-1.5 py-1 bg-surface2 border-b border-border2 min-w-0">
        <SlotPip slotKey={slotKey} size={13} />
        <span className="text-dim text-[10px] tracking-[0.06em] truncate">{label}</span>
      </div>
      {stats.length === 0 ? (
        <div className="aspect-square bg-surface2" />
      ) : (
        <Mosaic stats={stats} cardsByName={cardsByName} onExpand={() => setModalOpen(true)} />
      )}
      {stats.length > 0 && (
        <div className="px-1.5 py-1.5 flex items-center justify-between gap-1.5 min-w-0">
          <span className="text-subtle text-[10.5px] truncate min-w-0">
            {stats.length > 1 ? `${stats.length}-way tie` : stats[0].cardName}
          </span>
          <span className={`text-[13px] font-mono tabular-nums font-semibold shrink-0 ${toneClass}`}>
            {stats[0].pickCount} / {n}
          </span>
        </div>
      )}
      {modalOpen && (
        <TiedCardsModal
          label={label}
          stats={stats}
          cardsByName={cardsByName}
          n={n}
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  );
}

function Mosaic({
  stats,
  cardsByName,
  onExpand,
}: {
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  onExpand: () => void;
}) {
  const tied = stats.length > 1;
  const shown = stats.slice(0, MAX_MOSAIC);
  const overflow = stats.length - shown.length;
  const gridCls = shown.length === 2 ? "grid-cols-2" : "grid-cols-2 grid-rows-2";

  return (
    <div className="relative aspect-square group">
      {tied ? (
        <div className={`grid ${gridCls} gap-px h-full w-full bg-border2`}>
          {shown.map((stat, i) => {
            const card = cardsByName.get(stat.cardName);
            const spanLast = shown.length === 3 && i === shown.length - 1 ? "col-span-2" : "";
            return card ? (
              <CardImagePreview key={stat.cardName} imageUrl={card.imageNormal} alt={card.name} className={`overflow-hidden ${spanLast}`}>
                <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
              </CardImagePreview>
            ) : (
              <div key={stat.cardName} className={`bg-surface2 ${spanLast}`} />
            );
          })}
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

      {tied && (
        <button
          type="button"
          onClick={onExpand}
          className="absolute bottom-1 right-1 text-[10px] bg-bg/80 rounded-sm px-1 text-dim cursor-pointer pointer-events-auto"
          title={`${stats.length} cards tied — view all`}
        >
          &#128269;{overflow > 0 ? ` +${overflow}` : ""}
        </button>
      )}
    </div>
  );
}
