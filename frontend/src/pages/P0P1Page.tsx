import { AppHeader } from "../components/AppHeader";
import { Crossfade } from "../components/Crossfade";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SectionLabel } from "../components/SectionLabel";
import { ManaCost } from "../components/ManaPips";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { SlotPip, SLOT_ACCENT } from "../components/p0p1/slotVisuals";
import { P0P1ProgressBar } from "../components/p0p1/ProgressBar";
import { ClearAll } from "../components/p0p1/ClearAll";
import { P0P1Hero } from "../components/p0p1/P0P1Hero";
import { AutoSaveBadge } from "../components/p0p1/AutoSaveBadge";
import { P0P1MobileSelector } from "../components/p0p1/P0P1MobileView";
import { GoToTopButton } from "../components/GoToTopButton";
import { useIsMobile } from "../lib/use-is-mobile";
import { useP0P1Ballot } from "../data/useP0P1Ballot";
import { SLOTS } from "../data/p0p1Slots";
import type { Card, SlotDefinition, SlotKey } from "../types/p0p1";

export function P0P1Page() {
  const ballot = useP0P1Ballot();
  const {
    cards,
    cardsByName,
    dataReady,
    user,
    authLoading,
    signIn,
    picksBySlot,
    pickedExcept,
    pickedSlotLabels,
    scoringFilled,
    isComplete,
    isPastDeadline,
    handleClearAll,
    clearPending,
    setEditingSlotKey,
    activeSlotKey,
    activeSlot,
    selectAdvance,
  } = ballot;
  const isDesktop = !useIsMobile(1024);

  if (!isDesktop) {
    return <P0P1MobileSelector ballot={ballot} />;
  }

  const loginCta = !authLoading && !user && !isPastDeadline && (
    <button type="button" onClick={signIn} className="bg-transparent border-0 cursor-pointer p-0">
      <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
        LOG IN TO SUBMIT PICKS
      </CtaPill>
    </button>
  );

  const heroCta = loginCta || (user && !isPastDeadline ? <AutoSaveBadge complete={isComplete} /> : null);

  const teamProgress = !isPastDeadline && (
    <div className="flex items-center gap-3 w-full max-w-[420px]">
      <SectionLabel size={13}>PICKS</SectionLabel>
      <div className="flex-1">
        <P0P1ProgressBar filled={scoringFilled} total={SLOTS.length} isComplete={isComplete} />
      </div>
    </div>
  );

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="P0 P1 Challenge" />
      <P0P1Hero cta={heroCta} belowIntro={teamProgress} />

      <main className="flex-1 px-10 pb-5 pt-5">
        {dataReady ? (
          <RosterStrip
            activeSlotKey={activeSlotKey}
            picksBySlot={picksBySlot}
            cardsByName={cardsByName}
            locked={isPastDeadline}
            onSelect={(key) => setEditingSlotKey(key)}
          />
        ) : (
          <RosterStripSkeleton />
        )}

        {!isPastDeadline && (
          <div className="mt-4">
            {dataReady && cards ? (
              <Crossfade transitionKey={activeSlot.key}>
                <CardSelectionGrid
                  key={activeSlot.key}
                  animateMount={false}
                  slot={activeSlot}
                  cards={cards}
                  pickedCards={pickedExcept(activeSlot.key)}
                  takenBy={pickedSlotLabels}
                  selectedName={picksBySlot.get(activeSlot.key)}
                  onSelect={(name) => selectAdvance(activeSlot.key, name)}
                  minColW={200}
                  footerRight={
                    <ClearAll
                      onClear={handleClearAll}
                      clearing={clearPending}
                      visible={scoringFilled > 0}
                      className="shrink-0"
                    />
                  }
                />
              </Crossfade>
            ) : (
              <CardGridSkeleton />
            )}
          </div>
        )}
      </main>

      <GoToTopButton onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
    </div>
  );
}

function RosterStrip({
  activeSlotKey,
  picksBySlot,
  cardsByName,
  locked,
  onSelect,
}: {
  activeSlotKey: SlotKey;
  picksBySlot: Map<string, string>;
  cardsByName: Map<string, Card>;
  locked: boolean;
  onSelect: (key: SlotKey) => void;
}) {
  return (
    <div className="grid grid-cols-8 gap-2">
      {SLOTS.map((slot) => {
        const cardName = picksBySlot.get(slot.key);
        return (
          <RosterTile
            key={slot.key}
            slot={slot}
            card={cardName ? cardsByName.get(cardName) : undefined}
            active={!locked && activeSlotKey === slot.key}
            locked={locked}
            onClick={() => onSelect(slot.key)}
          />
        );
      })}
    </div>
  );
}

function RosterTile({
  slot,
  card,
  active,
  locked,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  locked: boolean;
  onClick: () => void;
}) {
  const accent = SLOT_ACCENT[slot.key];
  const stripClass = `w-full shrink-0 transition-[height] duration-150 ${active ? "h-2" : "h-1 group-hover:h-2"}`;
  const body = (
    <>
      <div className={stripClass} style={{ background: accent }} />
      <div className="flex-1 min-h-0 bg-surface2 flex items-center justify-center overflow-hidden">
        {card ? (
          <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
        ) : (
          <SlotPip slotKey={slot.key} size={48} />
        )}
      </div>
      <div className={`pl-4 pr-2.5 shrink-0 transition-[padding] duration-150 ${active ? "py-2.5" : "py-1.5 group-hover:py-2.5"}`}>
        <div className="text-subtle text-[12px] tracking-[0.12em] font-display truncate mb-1">
          {slot.label.toUpperCase()}
        </div>
        {card ? (
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="text-text text-[14px] truncate min-w-0">{card.name}</span>
            <span className="ml-auto shrink-0">
              <ManaCost cost={card.manaCost} size={13} />
            </span>
          </div>
        ) : (
          <span className={locked ? "text-dim text-[14px]" : "italic text-dim text-[13px]"}>
            {locked ? "—" : "Select a card"}
          </span>
        )}
      </div>
    </>
  );

  const base = "group relative flex flex-col aspect-square border border-t-0 overflow-hidden text-left min-w-0";
  if (locked) {
    return <div className={`${base} bg-surface border-border2`}>{body}</div>;
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${base} transition-colors cursor-pointer ${
        active ? "border-green/60 bg-green/5" : "border-border2 bg-surface hover:border-green/60"
      }`}
    >
      {body}
    </button>
  );
}

function RosterStripSkeleton() {
  return (
    <div className="grid grid-cols-8 gap-2">
      {Array.from({ length: SLOTS.length }, (_, i) => (
        <div key={i} className="flex flex-col aspect-square border-t-0 bg-surface border border-border2">
          <div className="h-1 w-full bg-surface2" />
          <div className="flex-1 min-h-0 bg-surface2 animate-pulse" />
          <div className="px-2.5 py-1.5 shrink-0 flex flex-col gap-1">
            <div className="h-2 w-12 bg-surface2 animate-pulse" />
            <div className="h-2.5 w-16 bg-surface2 animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <div className="h-5 w-40 bg-surface2 animate-pulse" />
        <div className="ml-auto h-7 w-60 bg-surface2 animate-pulse" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3.5">
        {Array.from({ length: 10 }, (_, i) => (
          <div key={i} className="bg-surface2 animate-pulse rounded-[3%]" style={{ aspectRatio: "488 / 680" }} />
        ))}
      </div>
    </div>
  );
}
