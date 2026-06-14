import { useCallback, useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SetGlyph, setGlyphCode } from "../components/Brand";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { SectionLabel } from "../components/SectionLabel";
import { SlotCard } from "../components/p0p1/SlotCard";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { useAuth } from "../auth/useAuth";
import { useIsMobile } from "../lib/use-is-mobile";
import {
  useP0P1Cards,
  useP0P1Picks,
  useUpsertP0P1Pick,
  useDeleteAllP0P1Picks,
  useSets,
} from "../data/hooks";
import {
  P0P1_SET_CODE as SET_CODE,
  P0P1_VOTING_DEADLINE as VOTING_DEADLINE,
  SLOTS,
  P0P1_SET_NAME,
} from "../data/p0p1Slots";
import { fmtRange } from "../data/utils";
import type { Card, SlotKey } from "../types/p0p1";
const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

export function P0P1Page() {
  const { user, loading: authLoading, signIn } = useAuth();
  const { data: cards } = useP0P1Cards(SET_CODE);
  const { data: picks } = useP0P1Picks(user ? SET_CODE : undefined);
  const upsertPick = useUpsertP0P1Pick(SET_CODE);
  const clearAll = useDeleteAllP0P1Picks(SET_CODE);
  const isDesktop = !useIsMobile(1024);
  const [editingSlotKey, setEditingSlotKey] = useState<SlotKey | null>(null);

  const cardsByName = useMemo(() => {
    if (!cards) return new Map<string, Card>();
    return new Map(cards.map((c) => [c.name, c]));
  }, [cards]);

  const picksBySlot = useMemo(() => {
    if (!picks) return new Map<string, string>();
    return new Map(picks.map((v) => [v.slot, v.cardName]));
  }, [picks]);

  const pickedCards = useMemo(
    () => new Set(picksBySlot.values()),
    [picksBySlot],
  );

  const filledCount = picksBySlot.size;
  const isComplete = filledCount === SLOTS.length;
  const isPastDeadline = new Date() > VOTING_DEADLINE;

  const defaultSlotKey = useMemo(
    () => SLOTS.find((s) => !picksBySlot.has(s.key))?.key ?? SLOTS[0].key,
    [picksBySlot],
  );
  const activeSlotKey = editingSlotKey ?? defaultSlotKey;
  const activeSlot = SLOTS.find((s) => s.key === activeSlotKey)!;

  const nextUnfilledSlot = useCallback(
    (afterKey: SlotKey, newPick: string) => {
      const idx = SLOTS.findIndex((s) => s.key === afterKey);
      for (let i = 1; i < SLOTS.length; i++) {
        const candidate = SLOTS[(idx + i) % SLOTS.length];
        if (!picksBySlot.has(candidate.key)) return candidate.key;
      }
      return afterKey;
    },
    [picksBySlot],
  );

  const slotList = (
    <div className="flex flex-col gap-2">
      {SLOTS.map((slot) => {
        const cardName = picksBySlot.get(slot.key);
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
              upsertPick.mutate({ slot: slot.key, cardName: name });
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

  const { data: allSets } = useSets();
  const p0p1Sets = useMemo(
    () => allSets?.filter((s) => s.code === SET_CODE),
    [allSets],
  );
  const setMeta = allSets?.find((s) => s.code === SET_CODE);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="Pack 0, Pick 1" />

      {isDesktop ? (
        <>
          <P0P1Hero setMeta={setMeta} sets={p0p1Sets} />
          <RulesBar />

          <main className="flex-1 flex flex-col px-10 pb-5">
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

            {user && !isPastDeadline && (
              <div
                className="grid gap-6 mt-4"
                style={{ gridTemplateColumns: "350px minmax(0, 1fr)" }}
              >
                {cards && picks ? (
                  <>
                    <div className="sticky top-20 self-start">
                      <ProgressBanner
                        filled={filledCount}
                        total={SLOTS.length}
                        isComplete={isComplete}
                        onClearAll={() => clearAll.mutate()}
                        clearing={clearAll.isPending}
                      />
                      <div className="mt-4">{slotList}</div>
                    </div>
                    <CardSelectionGrid
                      key={activeSlot.key}
                      slot={activeSlot}
                      cards={cards}
                      pickedCards={pickedCards}
                      onSelect={(name) => {
                        upsertPick.mutate({ slot: activeSlot.key, cardName: name });
                        setEditingSlotKey(nextUnfilledSlot(activeSlot.key, name));
                      }}
                    />
                  </>
                ) : (
                  <>
                    <div>
                      <div className="flex items-center justify-center px-4 py-3 border border-border2 bg-surface">
                        <div className="h-3 w-24 bg-surface2 animate-pulse" />
                      </div>
                      <div className="mt-4"><SlotsListSkeleton /></div>
                    </div>
                    <CardGridSkeleton />
                  </>
                )}
              </div>
            )}

            {user && cards && isPastDeadline && (
              <div className="mt-4">{slotList}</div>
            )}
          </main>

          <Footer className="mt-auto px-10 pt-5 pb-3" />
        </>
      ) : (
        <>
          <MobileSetStrip sets={p0p1Sets} />
          <main className="flex-1 flex flex-col mx-auto w-full max-w-[640px] px-5 pt-4 pb-5">
            <MobileRules />

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

            {user && (
              cards && picks ? (
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
              ) : (
                <>
                  <div className="flex items-center justify-center px-4 py-3 border border-border2 bg-surface">
                    <div className="h-3 w-24 bg-surface2 animate-pulse" />
                  </div>
                  <div className="mt-4"><SlotsListSkeleton /></div>
                </>
              )
            )}

            <Footer className="mt-auto pt-8" />
          </main>
        </>
      )}
    </div>
  );
}

function P0P1Hero({
  setMeta,
  sets,
}: {
  setMeta: import("../types/leaderboard").SetSummary | undefined;
  sets: import("../types/leaderboard").SetSummary[] | undefined;
}) {
  return (
    <div className="relative px-10 py-5 border-b border-border bg-surface flex items-center gap-6">
      <SetGlyph code={SET_CODE} size={84} />
      <div className="flex-1">
        <SectionLabel size={13}>PACK 0, PICK 1 Challenge</SectionLabel>
        <div className="flex items-baseline gap-3.5 mt-0.5">
          <span
            className="font-display tracking-[0.04em]"
            style={{ fontSize: 56, lineHeight: 0.9 }}
          >
            {SET_CODE}
          </span>
          <span className="font-display text-[22px] text-muted tracking-[0.06em]">
            {P0P1_SET_NAME.toUpperCase()}
          </span>
        </div>
        <div className="flex items-center gap-3 mt-1">
          {setMeta && (
            <span className="mono text-[11px] text-muted">
              {fmtRange(setMeta.startDate, setMeta.endDate)}
            </span>
          )}
          <CountdownInline deadline={VOTING_DEADLINE} />
        </div>
      </div>
      {sets && (
        <SetSwitcherDesktop
          sets={sets}
          activeCode={SET_CODE}
          onChange={() => {}}
        />
      )}
    </div>
  );
}

function RulesBar() {
  return (
    <div className="px-10 py-2.5 bg-surface border-b border-border flex items-center gap-6">
      <span className="text-[13px] text-muted leading-[1.6]">
        Pick your best card for each slot. Teams ranked by{" "}
        <a
          href={SEVENTEEN_LANDS_URL}
          target="_blank"
          rel="noreferrer"
          className="text-green hover:underline underline-offset-2"
        >
          17Lands GIH win rate
        </a>{" "}
        after six weeks.
      </span>
      <span className="text-[12px] text-dim whitespace-nowrap">
        Slot 9 = tiebreaker only · No duplicates · Auto-saves
      </span>
    </div>
  );
}

function MobileSetStrip({
  sets,
}: {
  sets: import("../types/leaderboard").SetSummary[] | undefined;
}) {
  return (
    <div className="px-3 pt-2 pb-1 border-b border-border bg-surface flex items-center gap-3">
      <div className="pl-1 pr-1">
        <SetGlyph
          code={setGlyphCode(sets?.find((s) => s.code === SET_CODE) ?? { code: SET_CODE })}
          size={32}
        />
      </div>
      <span
        className="font-display text-text tracking-[0.04em]"
        style={{ fontSize: 28, lineHeight: 1 }}
      >
        {SET_CODE}
      </span>
      {sets && sets.length > 0 && (
        <div className="ml-auto basis-[34%] min-w-0">
          <SetSwitcherMobile
            sets={sets}
            activeCode={SET_CODE}
            onChange={() => {}}
          />
        </div>
      )}
    </div>
  );
}

function MobileRules() {
  return (
    <section className="mb-4">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="font-display text-[15px] text-text tracking-[0.15em]">
          P0, P1 CHALLENGE
        </span>
        <CountdownInline deadline={VOTING_DEADLINE} />
      </div>
      <div className="text-[13px] text-muted leading-[1.6]">
        Pick your best card for each slot. Teams ranked by{" "}
        <a
          href={SEVENTEEN_LANDS_URL}
          target="_blank"
          rel="noreferrer"
          className="text-green hover:underline underline-offset-2"
        >
          17Lands GIH win rate
        </a>{" "}
        after six weeks.
      </div>
      <div className="text-[11px] text-dim mt-1">
        Slot 9 = tiebreaker only · No duplicates · Auto-saves
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
        {`${filled}/${total} slots filled`}
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

const SKEL_LABEL_W = [90, 75, 85, 65, 80, 120, 100, 110, 130];
const SKEL_NAME_W = [120, 100, 110, 95, 105, 130, 115, 125, 140];

function SlotCardSkeleton({ index }: { index: number }) {
  return (
    <div className="w-full flex items-center gap-4 px-4 py-3 bg-surface border border-border2">
      <div className="w-20 h-12 bg-surface2 animate-pulse shrink-0" />
      <div className="flex-1 flex flex-col gap-1.5">
        <div
          className="h-2 bg-surface2 animate-pulse"
          style={{ width: SKEL_LABEL_W[index % SKEL_LABEL_W.length] }}
        />
        <div
          className="h-3 bg-surface2 animate-pulse"
          style={{ width: SKEL_NAME_W[index % SKEL_NAME_W.length] }}
        />
      </div>
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div>
      <div className="h-4 w-32 bg-surface2 animate-pulse mb-3" />
      <div className="h-9 w-full bg-surface2 animate-pulse mb-3" />
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <div
            key={i}
            className="bg-surface2 animate-pulse rounded-lg"
            style={{ aspectRatio: "488 / 680" }}
          />
        ))}
      </div>
      <div className="h-3 w-24 bg-surface2 animate-pulse mt-3" />
    </div>
  );
}

function SlotsListSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 9 }, (_, i) => (
        <SlotCardSkeleton key={i} index={i} />
      ))}
    </div>
  );
}

function CountdownInline({ deadline }: { deadline: Date }) {
  const diff = deadline.getTime() - Date.now();
  if (diff <= 0) {
    return <span className="text-muted text-[13px]">Entries have closed</span>;
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  return (
    <span className="text-green text-[14px] whitespace-nowrap">
      Closes in {days} days, {hours} hours
    </span>
  );
}

