import { useState } from "react";
import type { MshCard, SlotDefinition } from "../../types/p0p1";
import { ManaCost } from "../ManaPips";
import { CardImagePreview } from "./CardImagePreview";
import { CardPicker } from "./CardPicker";

interface Props {
  slot: SlotDefinition;
  selectedCard: MshCard | undefined;
  allCards: MshCard[];
  pickedCards: Set<string>;
  onSelect: (cardName: string) => void;
}

export function SlotCard({
  slot,
  selectedCard,
  allCards,
  pickedCards,
  onSelect,
}: Props) {
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setPickerOpen(true)}
        className="w-full flex items-center gap-4 px-4 py-3 bg-surface border border-border2 hover:border-green transition-colors cursor-pointer text-left group"
      >
        {selectedCard ? (
          <>
            <CardImagePreview
              imageUrl={selectedCard.imageNormal}
              alt={selectedCard.name}
            >
              <img
                src={selectedCard.imageArtCrop}
                alt=""
                className="w-20 h-12 object-cover border border-border2"
              />
            </CardImagePreview>
            <div className="flex-1 min-w-0">
              <div className="text-muted text-[11px] tracking-[0.14em] font-display mb-0.5">
                {slot.label.toUpperCase()}
              </div>
              <div className="flex items-center gap-2">
                <div className="text-text text-[15px] truncate">
                  {selectedCard.name}
                </div>
                <ManaCost cost={selectedCard.manaCost} />
              </div>
            </div>
            <span className="text-dim text-[12px] group-hover:text-green transition-colors shrink-0">
              CHANGE
            </span>
          </>
        ) : (
          <>
            <div className="w-20 h-12 bg-surface2 border border-border2 shrink-0 flex items-center justify-center">
              <span className="text-dim text-[20px]">?</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-muted text-[11px] tracking-[0.14em] font-display mb-0.5">
                {slot.label.toUpperCase()}
              </div>
              <div className="text-dim text-[14px]">Select a card</div>
            </div>
          </>
        )}
      </button>

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
