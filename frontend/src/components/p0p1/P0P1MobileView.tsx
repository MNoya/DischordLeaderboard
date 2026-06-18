import { AppHeader } from "../AppHeader";
import { CtaPill } from "../CtaPill";
import { DiscordIcon } from "../BrandIcons";
import { SetGlyph, setGlyphCode } from "../Brand";
import { CardSelectionGrid } from "./CardSelectionGrid";
import { SlotPip, SLOT_ACCENT } from "./slotVisuals";
import { P0P1ProgressBar } from "./ProgressBar";
import { ClearAll } from "./ClearAll";
import { GoToTopButton } from "../GoToTopButton";
import type { useP0P1Ballot } from "../../data/useP0P1Ballot";
import {
  P0P1_SET_CODE as SET_CODE,
  P0P1_SET_NAME,
  P0P1_VOTING_DEADLINE as VOTING_DEADLINE,
  SLOTS,
} from "../../data/p0p1Slots";
import type { Card, SlotDefinition } from "../../types/p0p1";
import type { SetSummary } from "../../types/leaderboard";

const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

type Ballot = ReturnType<typeof useP0P1Ballot>;

export function P0P1MobileSelector({ ballot }: { ballot: Ballot }) {
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
    activeSlotKey,
    activeSlot,
    setEditingSlotKey,
    selectAdvance,
    p0p1Sets,
  } = ballot;

  const loginBarVisible = !authLoading && !user && !isPastDeadline;

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="P0 P1 Challenge" />

      <main className={`flex-1 flex flex-col w-full px-3 pt-3 ${loginBarVisible ? "pb-24" : "pb-4"}`}>
        <MobileIntro sets={p0p1Sets} />
        {dataReady ? (
          <>
            {!isPastDeadline && (
              <div className="mb-1.5">
                <P0P1ProgressBar
                  filled={scoringFilled}
                  total={SLOTS.length}
                  isComplete={isComplete}
                  doneLabel="PICKS SAVED"
                  doneHint="Edit anytime before deadline"
                />
              </div>
            )}
            <div className="sticky top-0 z-20 -mx-3 px-2 pt-3 pb-2 bg-bg/95 backdrop-blur border-b border-border">
              <div className="grid grid-cols-4 landscape:grid-cols-8 gap-1.5">
                {SLOTS.map((slot) => {
                  const cardName = picksBySlot.get(slot.key);
                  return (
                    <MobileChip
                      key={slot.key}
                      slot={slot}
                      card={cardName ? cardsByName.get(cardName) : undefined}
                      active={!isPastDeadline && activeSlotKey === slot.key}
                      onClick={() => setEditingSlotKey(slot.key)}
                    />
                  );
                })}
              </div>
            </div>

            {!isPastDeadline && cards && (
              <div className="pt-2">
                <CardSelectionGrid
                  key={activeSlot.key}
                  slot={activeSlot}
                  cards={cards}
                  pickedCards={pickedExcept(activeSlot.key)}
                  takenBy={pickedSlotLabels}
                  selectedName={picksBySlot.get(activeSlot.key)}
                  onSelect={(name) => selectAdvance(activeSlot.key, name)}
                  minColW={150}
                  showLabel={false}
                  autoFocusSearch={false}
                  leftLabel={
                    <>
                      <SlotPip slotKey={activeSlot.key} size={20} />
                      <span className="font-display text-[18px] tracking-[0.06em] truncate">{activeSlot.label}</span>
                    </>
                  }
                  footerRight={
                    <ClearAll
                      onClear={handleClearAll}
                      clearing={clearPending}
                      visible={scoringFilled > 0}
                      className="shrink-0"
                    />
                  }
                />
              </div>
            )}
          </>
        ) : (
          <>
            <div className="h-2 w-full bg-surface2 animate-pulse mb-3 rounded-full" />
            <div className="grid grid-cols-4 landscape:grid-cols-8 gap-1.5">
              {Array.from({ length: SLOTS.length }, (_, i) => (
                <div key={i} className="aspect-[5/4] landscape:aspect-auto landscape:h-14 bg-surface2 animate-pulse border border-border2" />
              ))}
            </div>
          </>
        )}
      </main>

      <MobileLoginBar show={loginBarVisible} signIn={signIn} />

      <GoToTopButton
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        compact
        bottomClass={loginBarVisible ? "bottom-20" : "bottom-4"}
      />
    </div>
  );
}

function MobileChip({
  slot,
  card,
  active,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  onClick: () => void;
}) {
  const accent = SLOT_ACCENT[slot.key];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={slot.label}
      className={`relative w-full aspect-[5/4] landscape:aspect-auto landscape:h-14 bg-surface2 overflow-hidden border border-t-0 transition-colors ${
        active ? "border-green" : "border-border2"
      }`}
    >
      <div
        className={`absolute top-0 left-0 right-0 z-10 transition-[height] duration-150 ${active ? "h-2" : "h-1"}`}
        style={{ background: accent }}
      />
      {card ? (
        <img src={card.imageArtCrop} alt="" className="w-full h-full object-cover" />
      ) : (
        <span className="absolute inset-0 flex items-center justify-center">
          <SlotPip slotKey={slot.key} size={20} />
        </span>
      )}
    </button>
  );
}

function MobileLoginBar({ show, signIn }: { show: boolean; signIn: () => void }) {
  if (!show) {
    return null;
  }
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-bg/95 backdrop-blur border-t border-border px-4 py-2.5 flex justify-center">
      <button type="button" onClick={signIn} className="bg-transparent border-0 cursor-pointer p-0">
        <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
          LOG IN TO SUBMIT PICKS
        </CtaPill>
      </button>
    </div>
  );
}

function MobileIntro({ sets }: { sets: SetSummary[] | undefined }) {
  return (
    <section className="bg-surface border border-border rounded-xl p-4 mb-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 shrink-0">
          <SetGlyph code={setGlyphCode(sets?.find((s) => s.code === SET_CODE) ?? { code: SET_CODE })} size={34} />
          <span className="font-display text-text tracking-[0.04em]" style={{ fontSize: 22, lineHeight: 1 }}>
            {SET_CODE}
          </span>
        </div>
        <span className="flex-1 text-center font-display text-[16px] text-text tracking-[0.1em]">PACK 0, PICK 1</span>
        <CountdownStacked deadline={VOTING_DEADLINE} />
      </div>
      <p className="text-subtle text-[13.5px] leading-[1.5]">
        Put together a team of eight cards from <span className="font-semibold text-text">{P0P1_SET_NAME}</span>. Six weeks
        after release, teams are ranked by their total{" "}
        <a
          href={SEVENTEEN_LANDS_URL}
          target="_blank"
          rel="noreferrer"
          className="text-green hover:underline underline-offset-2"
        >
          17Lands GIH win rate
        </a>
        .
      </p>
    </section>
  );
}

function CountdownStacked({ deadline }: { deadline: Date }) {
  const diff = deadline.getTime() - Date.now();
  if (diff <= 0) {
    return <span className="text-muted text-[13px] whitespace-nowrap">Entries have closed</span>;
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  return (
    <div className="flex flex-col items-end leading-tight whitespace-nowrap shrink-0">
      <span className="text-muted text-[11px] tracking-[0.04em]">Closes in</span>
      <span className="text-green text-[13px]">
        {days} days, {hours} hours
      </span>
    </div>
  );
}
