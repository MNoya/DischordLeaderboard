import { useCallback, useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SlotCard } from "../components/p0p1/SlotCard";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { useAuth } from "../auth/useAuth";
import { useIsMobile } from "../lib/use-is-mobile";
import { useP0P1Cards, useP0P1Entries, useUpsertP0P1Entry, useDeleteAllP0P1Entries } from "../data/hooks";
import { P0P1_SET_CODE as SET_CODE, P0P1_VOTING_DEADLINE as VOTING_DEADLINE, SLOTS } from "../data/p0p1Slots";
import type { MshCard, SlotKey } from "../types/p0p1";
const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

export function P0P1Page() {
  const { user, loading: authLoading, signIn } = useAuth();
  const { data: cards } = useP0P1Cards(SET_CODE);
  const { data: votes } = useP0P1Entries(user ? SET_CODE : undefined);
  const upsertVote = useUpsertP0P1Entry(SET_CODE);
  const clearAll = useDeleteAllP0P1Entries(SET_CODE);
  const isDesktop = !useIsMobile(1024);
  const [editingSlotKey, setEditingSlotKey] = useState<SlotKey | null>(null);

  const cardsByName = useMemo(() => {
    if (!cards) return new Map<string, MshCard>();
    return new Map(cards.map((c) => [c.name, c]));
  }, [cards]);

  const votesBySlot = useMemo(() => {
    if (!votes) return new Map<string, string>();
    return new Map(votes.map((v) => [v.slot, v.cardName]));
  }, [votes]);

  const pickedCards = useMemo(
    () => new Set(votesBySlot.values()),
    [votesBySlot],
  );

  const filledCount = votesBySlot.size;
  const isComplete = filledCount === SLOTS.length;
  const isPastDeadline = new Date() > VOTING_DEADLINE;
  const editingSlot = editingSlotKey ? SLOTS.find((s) => s.key === editingSlotKey) : undefined;

  const slotList = (
    <div className="flex flex-col gap-2">
      {SLOTS.map((slot) => {
        const cardName = votesBySlot.get(slot.key);
        const selectedCard = cardName ? cardsByName.get(cardName) : undefined;
        return (
          <SlotCard
            key={slot.key}
            slot={slot}
            selectedCard={selectedCard}
            allCards={cards!}
            pickedCards={pickedCards}
            locked={isPastDeadline}
            onSelect={(name) => {
              upsertVote.mutate({ slot: slot.key, cardName: name });
            }}
            {...(isDesktop && !isPastDeadline ? {
              onEdit: () => setEditingSlotKey(slot.key),
              active: editingSlotKey === slot.key,
            } : {})}
          />
        );
      })}
    </div>
  );

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="P0P1" />
      <main className={`flex-1 flex flex-col mx-auto w-full px-5 md:px-10 pt-5 md:pt-10 pb-5 ${isDesktop ? "max-w-[1100px]" : "max-w-[640px]"}`}>

        {!authLoading && !user && !isPastDeadline && (
          <div className="flex justify-center my-8">
            <button type="button" onClick={signIn} className="bg-transparent border-0 cursor-pointer p-0">
              <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
                LOG IN TO PARTICIPATE
              </CtaPill>
            </button>
          </div>
        )}

        {isDesktop ? (
          user && cards ? (
            <>
              {!isPastDeadline && (
                <ProgressBanner filled={filledCount} total={SLOTS.length} isComplete={isComplete} onClearAll={() => clearAll.mutate()} clearing={clearAll.isPending} />
              )}
              <div className="grid gap-6 mt-4" style={{ gridTemplateColumns: "minmax(0, 1fr) 340px" }}>
                <div>
                  {editingSlot ? (
                    <CardSelectionGrid
                      key={editingSlot.key}
                      slot={editingSlot}
                      cards={cards}
                      pickedCards={pickedCards}
                      onSelect={(name) => {
                        upsertVote.mutate({ slot: editingSlot.key, cardName: name });
                        setEditingSlotKey(null);
                      }}
                      onCancel={() => setEditingSlotKey(null)}
                    />
                  ) : (
                    <Rules />
                  )}
                </div>
                <div className="sticky top-20 self-start">
                  {slotList}
                </div>
              </div>
            </>
          ) : (
            <Rules />
          )
        ) : (
          <>
            <Rules />
            {user && cards && (
              <>
                {!isPastDeadline && (
                  <ProgressBanner filled={filledCount} total={SLOTS.length} isComplete={isComplete} onClearAll={() => clearAll.mutate()} clearing={clearAll.isPending} />
                )}
                <div className="mt-4">{slotList}</div>
              </>
            )}
          </>
        )}

        <Footer className="mt-auto pt-8" />
      </main>
    </div>
  );
}

function Rules() {
  return (
    <section className="mb-6">
      <h2 className="font-display text-[16px] md:text-[18px] text-text tracking-[0.18em] mb-3">
        PACK 0, PICK 1
      </h2>
      <Countdown deadline={VOTING_DEADLINE} />
      <div className="flex flex-col gap-3 text-[13px] md:text-[14px] text-muted leading-[1.6] mt-3">
        <p>
          Pick one card for each of 9 slots. After 6 weeks, rosters are ranked by the
          sum of slots 1–8's{" "}
          <a
            href={SEVENTEEN_LANDS_URL}
            target="_blank"
            rel="noreferrer"
            className="text-green hover:underline underline-offset-2"
          >
            17Lands.com's GIH win rate metric
          </a>
          .
        </p>
        <p>Slot 9 will only be used in case of a tie.</p>
        <div className="bg-surface border border-border2 px-4 py-3">
          <table className="w-full text-[12px] md:text-[13px]">
            <thead>
              <tr className="text-left text-muted">
                <th className="font-display tracking-[0.1em] pb-1.5 font-normal">#</th>
                <th className="font-display tracking-[0.1em] pb-1.5 font-normal">SLOT</th>
                <th className="font-display tracking-[0.1em] pb-1.5 font-normal">CONSTRAINT</th>
              </tr>
            </thead>
            <tbody className="text-text">
              <SlotRow n={1} slot="White Common" constraint="Mono-white commons" />
              <SlotRow n={2} slot="Blue Common" constraint="Mono-blue commons" />
              <SlotRow n={3} slot="Black Common" constraint="Mono-black commons" />
              <SlotRow n={4} slot="Red Common" constraint="Mono-red commons" />
              <SlotRow n={5} slot="Green Common" constraint="Mono-green commons" />
              <SlotRow n={6} slot="Multicolor Uncommon" constraint="2+ color uncommons" />
              <SlotRow n={7} slot="Wildcard Common" constraint="Any common not already picked" />
              <SlotRow n={8} slot="Wildcard Uncommon" constraint="Any uncommon not already picked" />
              <SlotRow n={9} slot="Best Hero" constraint="Any Hero creature card below mythic as a tiebreaker - NOT included in score" />
            </tbody>
          </table>
        </div>
        <p className="text-[12px] text-muted">
          No card may appear in more than one slot. Picks auto-save and can be changed
          until the deadline.
        </p>
      </div>
    </section>
  );
}

function SlotRow({ n, slot, constraint }: { n: number; slot: string; constraint: string }) {
  return (
    <tr className="border-t border-border">
      <td className="py-1.5 text-dim pr-2">{n}</td>
      <td className="py-1.5 pr-3 whitespace-nowrap">{slot}</td>
      <td className="py-1.5 text-muted">{constraint}</td>
    </tr>
  );
}

function ProgressBanner({ filled, total, isComplete, onClearAll, clearing }: {
  filled: number; total: number; isComplete: boolean;
  onClearAll: () => void; clearing: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);

  const handleClear = useCallback(() => {
    if (!confirming) { setConfirming(true); return; }
    setConfirming(false);
    onClearAll();
  }, [confirming, onClearAll]);

  const showClear = filled > 0 && !isComplete && !clearing;

  return (
    <div
      className={`flex items-center justify-between px-4 py-3 border text-[13px] ${
        isComplete
          ? "border-green bg-green/10 text-green"
          : "border-border2 bg-surface text-muted"
      }`}
    >
      <span className="flex-1 text-center">
        {isComplete
          ? "Your roster is complete!"
          : `${filled}/${total} slots filled — your roster is incomplete`}
      </span>
      {showClear && (
        <button
          type="button"
          onClick={handleClear}
          className={`ml-3 shrink-0 bg-transparent border-0 text-[12px] cursor-pointer transition-colors ${
            confirming ? "text-red font-semibold" : "text-muted hover:text-red"
          }`}
        >
          {confirming ? "Sure?" : "Clear all picks"}
        </button>
      )}
    </div>
  );
}

function Countdown({ deadline }: { deadline: Date }) {
  const now = new Date();
  const diff = deadline.getTime() - now.getTime();
  if (diff <= 0) {
    return (
      <div className="px-4 py-3 border border-border2 bg-surface text-muted text-[13px] text-center">
        Voting has closed.
      </div>
    );
  }

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);

  return (
    <div className="px-4 py-3 border border-green bg-surface text-center">
      <span className="text-[14px] md:text-[16px] text-green">
        {days} days, {hours} hours remaining
      </span>
    </div>
  );
}
