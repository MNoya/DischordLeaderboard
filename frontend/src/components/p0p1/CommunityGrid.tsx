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
        tone="cyan"
        entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: extremesBySlot.get(slot.key)!.most }))}
        cardsByName={cardsByName}
        n={n}
      />
      <PickRow
        title="LEAST PICKED CARDS"
        tone="magenta"
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
  tone: "cyan" | "magenta";
  entries: { slotKey: SlotKey; label: string; stats: P0P1PickStat[] }[];
  cardsByName: Map<string, Card>;
  n: number;
}) {
  return (
    <div>
      <SectionLabel size={16} color={'white'} className="mb-2">
        {title}
      </SectionLabel>
      <div className="grid grid-cols-4 lg:grid-cols-8 gap-2">
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
  tone: "cyan" | "magenta";
  n: number;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const toneClass = tone === "cyan" ? "text-cyan" : "text-magenta";
  const hasStats = stats.length > 0;
  const tied = stats.length > 1;
  const overflow = stats.length - MAX_MOSAIC;

  return (
    <div className="flex flex-col border border-border2 bg-surface overflow-hidden min-w-0">
      <div className="relative aspect-square bg-surface2 overflow-hidden">
        {hasStats && <Mosaic stats={stats} cardsByName={cardsByName} />}
        <div
          className="absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center bg-bg/85"
          title={label}
        >
          <SlotPip slotKey={slotKey} size={12} />
        </div>
        {hasStats && (
          <span className={`absolute top-1 right-1 text-[9px] font-mono tabular-nums px-1 rounded-sm bg-bg/85 ${toneClass}`}>
            {stats[0].pickCount}/{n}
          </span>
        )}
        {tied && (
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="absolute bottom-1 right-1 text-[10px] bg-bg/80 rounded-sm px-1 text-dim cursor-pointer"
            title={`${stats.length} cards tied — view all`}
          >
            &#128269;{overflow > 0 ? ` +${overflow}` : ""}
          </button>
        )}
      </div>
      {hasStats && (
        <div className="px-1.5 py-1.5 min-w-0">
          <span className="text-subtle text-[10.5px] truncate block min-w-0">
            {tied ? `${stats.length}-way tie` : stats[0].cardName}
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

function Mosaic({ stats, cardsByName }: { stats: P0P1PickStat[]; cardsByName: Map<string, Card> }) {
  const tied = stats.length > 1;

  if (!tied) {
    const card = cardsByName.get(stats[0].cardName);
    return card ? (
      <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-full h-full">
        <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
      </CardImagePreview>
    ) : (
      <div className="w-full h-full bg-surface2" />
    );
  }

  const shown = stats.slice(0, MAX_MOSAIC);
  const gridCls = shown.length === 2 ? "grid-cols-2" : "grid-cols-2 grid-rows-2";
  return (
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
  );
}
