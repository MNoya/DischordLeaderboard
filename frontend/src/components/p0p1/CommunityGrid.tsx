import { useState } from "react";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { TiedCardsModal } from "./TiedCardsModal";
import { SectionLabel } from "../SectionLabel";
import { groupBySlot, findExtremes, participantCount } from "../../data/p0p1Stats";
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
  const mostBySlot = new Map(SLOTS.map((slot) => [slot.key, findExtremes(grouped.get(slot.key) ?? []).most]));
  const n = participantCount(pickStats);

  return (
    <PickRow
      title="Crowd Favorites"
      subtitle="Most popular picks by slot"
      entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: mostBySlot.get(slot.key)! }))}
      cardsByName={cardsByName}
      n={n}
    />
  );
}

function PickRow({
  title,
  subtitle,
  entries,
  cardsByName,
  n,
}: {
  title: string;
  subtitle: string;
  entries: { slotKey: SlotKey; label: string; stats: P0P1PickStat[] }[];
  cardsByName: Map<string, Card>;
  n: number;
}) {
  return (
    <div>
      <div className="flex flex-col mb-2">
        <SectionLabel size={16} color={'white'}>
          {title}
        </SectionLabel>
        <p className="text-dim text-[12px]">
          {subtitle}
        </p>
      </div>
      <div className="grid grid-cols-4 lg:grid-cols-8 gap-2">
        {entries.map(({ slotKey, label, stats }) => (
          <PickTile key={slotKey} slotKey={slotKey} label={label} stats={stats} cardsByName={cardsByName} n={n} />
        ))}
      </div>
    </div>
  );
}

function PickTile({
  slotKey,
  label,
  stats,
  cardsByName,
  n,
}: {
  slotKey: SlotKey;
  label: string;
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  n: number;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const hasStats = stats.length > 0;
  const tied = stats.length > 1;
  const card = hasStats ? cardsByName.get(stats[0].cardName) : undefined;

  return (
    <div className="flex flex-col border border-border2 bg-surface overflow-hidden min-w-0">
      <div className="relative aspect-square bg-surface2 overflow-hidden">
        {hasStats && (
          card ? (
            <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-full h-full">
              <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
            </CardImagePreview>
          ) : (
            <div className="w-full h-full bg-surface2" />
          )
        )}
        <div
          className="absolute top-1 left-1 w-5 h-5 rounded-full flex items-center justify-center bg-bg/85"
          title={label}
        >
          <SlotPip slotKey={slotKey} size={12} />
        </div>
        {tied && (
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="absolute top-1 right-1 text-[9px] font-display tracking-wide bg-bg/90 rounded-sm px-1 text-muted cursor-pointer"
            title={`${stats.length} cards tied at this count — view all`}
          >
            {stats.length}-WAY TIE
          </button>
        )}
        {hasStats && (
          <span className={`absolute bottom-1 right-1 text-[9px] font-mono tabular-nums px-1 rounded-sm bg-bg/85`}>
            {stats[0].pickCount} picked
          </span>
        )}
      </div>
      {hasStats && (
        <div className="px-1.5 py-1.5 min-w-0">
          <span className="text-subtle text-[10.5px] truncate block min-w-0">
            {stats[0].cardName}
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
