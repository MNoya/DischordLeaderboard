import { useCallback, useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SlotCard } from "../components/p0p1/SlotCard";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { useAuth } from "../auth/useAuth";
import { useIsMobile } from "../lib/use-is-mobile";
import {
  useP0P1Cards,
  useP0P1Entries,
  useUpsertP0P1Entry,
  useDeleteAllP0P1Entries,
} from "../data/hooks";
import {
  P0P1_SET_CODE as SET_CODE,
  P0P1_VOTING_DEADLINE as VOTING_DEADLINE,
  SLOTS,
  P0P1_SET_NAME,
} from "../data/p0p1Slots";
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

  const defaultSlotKey = useMemo(
    () => SLOTS.find((s) => !votesBySlot.has(s.key))?.key ?? SLOTS[0].key,
    [votesBySlot],
  );
  const activeSlotKey = editingSlotKey ?? defaultSlotKey;
  const activeSlot = SLOTS.find((s) => s.key === activeSlotKey)!;

  const nextUnfilledSlot = useCallback(
    (afterKey: SlotKey, newPick: string) => {
      const idx = SLOTS.findIndex((s) => s.key === afterKey);
      const nextPicked = new Set(votesBySlot.values());
      nextPicked.add(newPick);
      for (let i = 1; i < SLOTS.length; i++) {
        const candidate = SLOTS[(idx + i) % SLOTS.length];
        if (!votesBySlot.has(candidate.key)) return candidate.key;
      }
      return afterKey;
    },
    [votesBySlot],
  );

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
            {...(isDesktop && !isPastDeadline
              ? {
                  onEdit: () => setEditingSlotKey(slot.key),
                  active: activeSlotKey === slot.key,
                }
              : {})}
          />
        );
      })}
    </div>
  );

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="P0P1" />
      <main
        className={`flex-1 flex flex-col mx-auto w-full px-5 md:px-10 pt-5 md:pt-10 pb-5 ${isDesktop ? "max-w-[1100px]" : "max-w-[640px]"}`}
      >
        {isDesktop ? (
          <>
            <CompactRules />

            {!authLoading && !user && !isPastDeadline && (
              <div className="flex justify-center my-8">
                <button
                  type="button"
                  onClick={signIn}
                  className="bg-transparent border-0 cursor-pointer p-0"
                >
                  <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
                    LOG IN TO PARTICIPATE
                  </CtaPill>
                </button>
              </div>
            )}

            {user && cards && !isPastDeadline && (
              <>
                <div
                  className="grid gap-6 mt-4"
                  style={{ gridTemplateColumns: "340px minmax(0, 1fr)" }}
                >
                  <div className="sticky top-20 self-start">
                    <ProgressBanner
                    filled={filledCount}
                    total={SLOTS.length}
                    isComplete={isComplete}
                    onClearAll={() => clearAll.mutate()}
                    clearing={clearAll.isPending}
                  />
                  <div className="mt-4">

                    {slotList}
                  </div>
                  </div>
                  <CardSelectionGrid
                    key={activeSlot.key}
                    slot={activeSlot}
                    cards={cards}
                    pickedCards={pickedCards}
                    dismissable={false}
                    onSelect={(name) => {
                      upsertVote.mutate({ slot: activeSlot.key, cardName: name });
                      setEditingSlotKey(nextUnfilledSlot(activeSlot.key, name));
                    }}
                    onCancel={() => {}}
                  />
                </div>
              </>
            )}

            {user && cards && isPastDeadline && (
              <div className="mt-4">{slotList}</div>
            )}
          </>
        ) : (
          <>
            <Rules />

            {!authLoading && !user && !isPastDeadline && (
              <div className="flex justify-center my-8">
                <button
                  type="button"
                  onClick={signIn}
                  className="bg-transparent border-0 cursor-pointer p-0"
                >
                  <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
                    LOG IN TO PARTICIPATE
                  </CtaPill>
                </button>
              </div>
            )}

            {user && cards && (
              <>
                {!isPastDeadline && (
                  <ProgressBanner
                    filled={filledCount}
                    total={SLOTS.length}
                    isComplete={isComplete}
                    onClearAll={() => clearAll.mutate()}
                    clearing={clearAll.isPending}
                  />
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

function CompactRules() {
  return (
    <section className="mb-4">
      <div className="flex items-baseline justify-between gap-4 mb-3">
        <h2 className="font-display text-[18px] text-text tracking-[0.18em]">
          Pack 0, Pick 1 Challenge - {P0P1_SET_NAME}
        </h2>
        <CountdownInline deadline={VOTING_DEADLINE} />
      </div>
      <p className="text-[13px] text-muted leading-[1.6]">
        Pick your best card for each slot. Teams ranked by{" "}
        <a
          href={SEVENTEEN_LANDS_URL}
          target="_blank"
          rel="noreferrer"
          className="text-green hover:underline underline-offset-2"
        >
          17Lands GIH win rate
        </a>{" "}
        after six weeks. Slot 9 is tiebreaker only. Picks auto-save.
      </p>
    </section>
  );
}

function Rules() {
  return (
    <section className="mb-6">
      <h2 className="font-display text-[16px] md:text-[18px] text-text tracking-[0.18em] mb-3">
        Pack 0, Pick 1 Challenge - {P0P1_SET_NAME}
      </h2>
      <Countdown deadline={VOTING_DEADLINE} />
      <div className="flex flex-col gap-3 text-[13px] md:text-[14px] text-muted leading-[1.6] mt-3">
        <p>
          Pick a team of the cards you think will perform best in each of eight
          slots. After six weeks, teams will be ranked by the sum of the cards'{" "}
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
        <p>
          You will pick a card for the ninth slot, but it will only be used in
          case of a tie.
        </p>
        <p className="text-[12px] text-dim">
          No card may appear in more than one slot. Picks auto-save and can be
          changed until the deadline.
        </p>
      </div>
    </section>
  );
}


function ProgressBanner({
  filled,
  total,
  isComplete,
  onClearAll,
  clearing,
}: {
  filled: number;
  total: number;
  isComplete: boolean;
  onClearAll: () => void;
  clearing: boolean;
}) {
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);

  const handleClear = useCallback(() => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onClearAll();
  }, [confirming, onClearAll]);

  const showClear = filled > 0 && !clearing;

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
          ? "All slots filled. Your team is registered."
          : `${filled}/${total} slots filled`}
      </span>
      {showClear && (
        <button
          type="button"
          onClick={handleClear}
          className={`ml-3 shrink-0 bg-transparent border-0 text-[12px] cursor-pointer transition-colors ${
            confirming ? "text-red font-semibold" : "text-muted hover:text-red"
          }`}
        >
          {confirming ? "Sure?" : "CLEAR ALL PICKS"}
        </button>
      )}
    </div>
  );
}

function CountdownInline({ deadline }: { deadline: Date }) {
  const diff = deadline.getTime() - Date.now();
  if (diff <= 0) {
    return <span className="text-muted text-[13px]">Voting closed</span>;
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  return (
    <span className="text-green text-[14px] whitespace-nowrap">
      {days}d {hours}h remaining
    </span>
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
