import { useState } from "react";
import { SlotPip } from "./slotVisuals";
import { CardImagePreview } from "./CardImagePreview";
import { TiedCardsModal } from "./TiedCardsModal";
import { SectionLabel } from "../SectionLabel";
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
  const extremesBySlot = new Map(SLOTS.map((slot) => [slot.key, findExtremes(grouped.get(slot.key) ?? [])]));

  return (
    <div className="flex flex-col gap-6">
      <PickRow
        title="MOST PICKED CARDS"
        tone="green"
        entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: extremesBySlot.get(slot.key)!.most }))}
        cardsByName={cardsByName}
      />
      <PickRow
        title="LEAST PICKED CARDS"
        tone="red"
        entries={SLOTS.map((slot) => ({ slotKey: slot.key, label: slot.label, stats: extremesBySlot.get(slot.key)!.least }))}
        cardsByName={cardsByName}
      />
    </div>
  );
}

function PickRow({
  title,
  tone,
  entries,
  cardsByName,
}: {
  title: string;
  tone: "green" | "red";
  entries: { slotKey: SlotKey; label: string; stats: P0P1PickStat[] }[];
  cardsByName: Map<string, Card>;
}) {
  return (
    <div>
      <SectionLabel size={13} color={tone === "green" ? "#2ee85c" : "#ff5e5e"} className="mb-2">
        {title}
      </SectionLabel>
      <div className="grid grid-cols-8 gap-2">
        {entries.map(({ slotKey, label, stats }) => (
          <PickTile key={slotKey} slotKey={slotKey} label={label} stats={stats} tone={tone} cardsByName={cardsByName} />
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
}: {
  slotKey: SlotKey;
  label: string;
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  tone: "green" | "red";
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
        <PickArt stats={stats} cardsByName={cardsByName} toneClass={toneClass} onExpand={() => setModalOpen(true)} />
      )}
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

function PickArt({
  stats,
  cardsByName,
  toneClass,
  onExpand,
}: {
  stats: P0P1PickStat[];
  cardsByName: Map<string, Card>;
  toneClass: string;
  onExpand: () => void;
}) {
  const tied = stats.length > 1;
  const top = stats[0];
  const card = cardsByName.get(top.cardName);

  return (
    <div className="relative aspect-square group">
      {card ? (
        <CardImagePreview imageUrl={card.imageNormal} alt={card.name} className="w-full h-full">
          <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
        </CardImagePreview>
      ) : (
        <div className="w-full h-full bg-surface2" />
      )}

      {tied && (
        <button
          type="button"
          onClick={onExpand}
          className="absolute top-1 right-1 text-[10px] font-mono px-1 py-0.5 rounded bg-black/60 text-white border border-white/20 cursor-pointer pointer-events-auto"
        >
          {stats.length > 4 ? `+${stats.length}` : `${stats.length}-way`}
        </button>
      )}

      <div className="absolute bottom-0 left-0 right-0 px-1.5 py-1 bg-gradient-to-t from-black/70 to-transparent pointer-events-none flex items-center justify-between gap-1">
        <span className="text-white text-[11px] truncate">{tied ? `${stats.length}-way tie` : top.cardName}</span>
        <span className={`text-[12px] font-mono tabular-nums shrink-0 ${toneClass}`}>{top.pickPct}%</span>
      </div>
    </div>
  );
}
