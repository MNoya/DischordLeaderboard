import { useState } from "react";
import type { MshCard, SlotDefinition } from "../../types/p0p1";
import { CardImagePreview } from "./CardImagePreview";
import { CardPicker } from "./CardPicker";

interface Props {
  slot: SlotDefinition;
  selectedCard: MshCard | undefined;
  allCards: MshCard[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
}

export function SlotCard({ slot, selectedCard, allCards, pickedCards, onSelect }: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <>
      <div className="w-full flex items-center gap-4 px-4 py-3 bg-surface border border-border2 hover:border-green transition-colors group">
        {selectedCard ? (
          <>
            <CardImagePreview imageUrl={selectedCard.imageNormal} alt={selectedCard.name}>
              <img
                src={selectedCard.imageArtCrop}
                alt=""
                className="w-20 h-12 object-cover border border-border2"
              />
            </CardImagePreview>
            <button
              type="button"
              onClick={() => setPickerOpen(true)}
              className="flex-1 min-w-0 text-left bg-transparent border-0 cursor-pointer p-0"
            >
              <div className="text-muted text-[11px] tracking-[0.14em] font-display mb-0.5">
                {slot.label.toUpperCase()}
              </div>
              <div className="text-text text-[15px] truncate">{selectedCard.name}</div>
              <div className="text-muted text-[12px]">
                {selectedCard.manaCost.replace(/\{([^}]+)\}/g, "$1 ").trim() || "—"}
              </div>
            </button>
            <span
              onClick={() => setPickerOpen(true)}
              className="text-dim text-[12px] group-hover:text-green transition-colors shrink-0 cursor-pointer"
            >
              CHANGE
            </span>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className="w-full flex items-center gap-4 bg-transparent border-0 cursor-pointer p-0 text-left"
          >
            <div className="w-20 h-12 bg-surface2 border border-border2 shrink-0 flex items-center justify-center">
              <span className="text-dim text-[20px]">?</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-muted text-[11px] tracking-[0.14em] font-display mb-0.5">
                {slot.label.toUpperCase()}
              </div>
              <div className="text-dim text-[14px]">Select a card</div>
            </div>
          </button>
        )}
      </div>

      {pickerOpen && (
        <CardPicker
          slot={slot}
          cards={allCards}
          pickedCards={pickedCards}
          onSelect={(name) => {
            onSelect(name);
            setPickerOpen(false);
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </>
  );
}
