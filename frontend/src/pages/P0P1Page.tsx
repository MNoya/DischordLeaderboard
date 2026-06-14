import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SetGlyph, setGlyphCode } from "../components/Brand";
import { SectionLabel } from "../components/SectionLabel";
import { SlotCard } from "../components/p0p1/SlotCard";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { SlotPip } from "../components/p0p1/slotVisuals";
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
import { useLocalP0P1Picks, setLocalPick, clearLocalPicks, getLocalPicks } from "../data/localPicks";
import type { Card, SlotKey } from "../types/p0p1";

const SEVENTEEN_LANDS_URL = "https://www.17lands.com/card_data";

export function P0P1Page() {
  const { user, loading: authLoading, signIn } = useAuth();
  const { data: cards } = useP0P1Cards(SET_CODE);
  const { data: serverPicks } = useP0P1Picks(user ? SET_CODE : undefined);
  const localPicks = useLocalP0P1Picks(SET_CODE);
  const upsertPick = useUpsertP0P1Pick(SET_CODE);
  const clearAll = useDeleteAllP0P1Picks(SET_CODE);
  const isDesktop = !useIsMobile(1024);
  const [editingSlotKey, setEditingSlotKey] = useState<SlotKey | null>(null);

  const heroRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLDivElement>(null);
  const [heroHeight, setHeroHeight] = useState(0);
  const [navHeight, setNavHeight] = useState(0);
  useEffect(() => {
    const measure = () => {
      setHeroHeight(heroRef.current?.offsetHeight ?? 0);
      setNavHeight(navRef.current?.offsetHeight ?? 0);
    };
    measure();
    const obs = new ResizeObserver(measure);
    if (heroRef.current) obs.observe(heroRef.current);
    if (navRef.current) obs.observe(navRef.current);
    return () => obs.disconnect();
  }, [isDesktop]);

  const syncDone = useRef(false);
  useEffect(() => {
    if (!user || !serverPicks || syncDone.current) return;
    syncDone.current = true;
    const local = getLocalPicks(SET_CODE);
    if (local.length === 0) return;
    const serverSlots = new Set(serverPicks.map((p) => p.slot));
    const toSync = local.filter((p) => !serverSlots.has(p.slot));
    for (const p of toSync) {
      upsertPick.mutate({ slot: p.slot, cardName: p.cardName });
    }
    clearLocalPicks(SET_CODE);
  }, [user, serverPicks, upsertPick]);

  const activePicks = authLoading ? undefined : (user ? serverPicks : localPicks);
  const dataReady = cards && activePicks !== undefined;

  const persistPick = useCallback(
    (slot: SlotKey, cardName: string) => {
      if (user) {
        upsertPick.mutate({ slot, cardName });
      } else {
        setLocalPick(SET_CODE, slot, cardName);
      }
    },
    [user, upsertPick],
  );

  const handleClearAll = useCallback(() => {
    if (user) {
      clearAll.mutate();
    } else {
      clearLocalPicks(SET_CODE);
    }
  }, [user, clearAll]);

  const cardsByName = useMemo(() => {
    if (!cards) return new Map<string, Card>();
    return new Map(cards.map((c) => [c.name, c]));
  }, [cards]);

  const picksBySlot = useMemo(() => {
    if (!activePicks) return new Map<string, string>();
    return new Map(activePicks.map((v) => [v.slot, v.cardName]));
  }, [activePicks]);

  const pickedCards = useMemo(() => new Set(picksBySlot.values()), [picksBySlot]);

  const pickedExcept = useCallback(
    (slotKey: SlotKey) => {
      const own = picksBySlot.get(slotKey);
      if (!own) return pickedCards;
      const rest = new Set(pickedCards);
      rest.delete(own);
      return rest;
    },
    [pickedCards, picksBySlot],
  );

  const scoringFilled = SLOTS.filter((s) => picksBySlot.has(s.key)).length;
  const isComplete = scoringFilled === SLOTS.length;
  const isPastDeadline = new Date() > VOTING_DEADLINE;

  const defaultSlotKey = useMemo(
    () => SLOTS.find((s) => !picksBySlot.has(s.key))?.key ?? SLOTS[0].key,
    [picksBySlot],
  );
  const desktopSlotKey = editingSlotKey ?? defaultSlotKey;
  const desktopSlot = SLOTS.find((s) => s.key === desktopSlotKey)!;

  const nextUnfilledSlot = useCallback(
    (afterKey: SlotKey) => {
      const idx = SLOTS.findIndex((s) => s.key === afterKey);
      if (idx === -1) return afterKey;
      for (let i = 1; i < SLOTS.length; i++) {
        const candidate = SLOTS[(idx + i) % SLOTS.length];
        if (!picksBySlot.has(candidate.key)) return candidate.key;
      }
      return afterKey;
    },
    [picksBySlot],
  );

  const selectDesktop = useCallback(
    (slot: SlotKey, cardName: string) => {
      persistPick(slot, cardName);
      setEditingSlotKey(nextUnfilledSlot(slot));
    },
    [persistPick, nextUnfilledSlot],
  );

  const selectMobile = useCallback(
    (slot: SlotKey, cardName: string) => {
      persistPick(slot, cardName);
      setEditingSlotKey(null);
    },
    [persistPick],
  );

  const slotCard = (slotKey: SlotKey) => {
    const slot = SLOTS.find((s) => s.key === slotKey)!;
    const cardName = picksBySlot.get(slotKey);
    return (
      <SlotCard
        key={slotKey}
        slot={slot}
        selectedCard={cardName ? cardsByName.get(cardName) : undefined}
        locked={isPastDeadline}
        active={isDesktop && !isPastDeadline && desktopSlotKey === slotKey}
        onEdit={() => setEditingSlotKey(slotKey)}
      />
    );
  };

  const loginCta = !authLoading && !user && !isPastDeadline && (
    <button type="button" onClick={signIn} className="bg-transparent border-0 cursor-pointer p-0">
      <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
        LOG IN TO SUBMIT PICKS
      </CtaPill>
    </button>
  );

  const { data: allSets } = useSets();
  const p0p1Sets = useMemo(() => allSets?.filter((s) => s.code === SET_CODE), [allSets]);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <div ref={navRef}>
        <AppHeader subtitle="P0P1 Challenge" />
      </div>

      {isDesktop ? (
        <>
          <P0P1Hero cta={loginCta} innerRef={heroRef} />

          <main className="flex-1 flex flex-col px-10 pb-5">
            {!isPastDeadline && (
              <div className="grid gap-6 mt-5" style={{ gridTemplateColumns: "360px minmax(0, 1fr)" }}>
                {dataReady ? (
                  <>
                    <div
                      className="sticky self-start flex flex-col"
                      style={{ top: heroHeight + 8, height: `calc(100vh - ${navHeight + heroHeight + 36}px)` }}
                    >
                      <div className="h-8 flex flex-col justify-center">
                        <ProgressBar filled={scoringFilled} total={SLOTS.length} isComplete={isComplete} />
                      </div>
                      <div className="mt-3 flex-1 min-h-0 overflow-y-auto no-scrollbar flex flex-col gap-2">
                        {SLOTS.map((s) => (
                          <div key={s.key} className="flex-1 min-h-[56px] max-h-[84px]">
                            {slotCard(s.key)}
                          </div>
                        ))}
                      </div>
                      <ClearAll onClear={handleClearAll} clearing={user ? clearAll.isPending : false} visible={scoringFilled > 0} />
                    </div>
                    <CardSelectionGrid
                      key={desktopSlot.key}
                      slot={desktopSlot}
                      cards={cards}
                      pickedCards={pickedExcept(desktopSlot.key)}
                      selectedName={picksBySlot.get(desktopSlot.key)}
                      onSelect={(name) => selectDesktop(desktopSlot.key, name)}
                      minColW={190}
                    />
                  </>
                ) : (
                  <>
                    <div>
                      <div className="h-3 w-40 bg-surface2 animate-pulse" />
                      <div className="mt-3"><SlotsListSkeleton /></div>
                    </div>
                    <CardGridSkeleton />
                  </>
                )}
              </div>
            )}

            {cards && isPastDeadline && (
              <div className="mt-5 max-w-[640px] flex flex-col gap-1.5">
                {SLOTS.map((s) => slotCard(s.key))}
              </div>
            )}
          </main>
        </>
      ) : (
        <>
          <main className="flex-1 flex flex-col w-full px-4 pt-4 pb-20">
            <MobileIntro sets={p0p1Sets} />
            {dataReady ? (
              <>
                {!isPastDeadline && (
                  <div className="mb-3">
                    <ProgressBar filled={scoringFilled} total={SLOTS.length} isComplete={isComplete} />
                  </div>
                )}
                <div className="flex-1 min-h-0 flex flex-col gap-1.5">
                  {SLOTS.map((s) => (
                    <div key={s.key} className="flex-1 min-h-[56px]">
                      {slotCard(s.key)}
                    </div>
                  ))}
                </div>
                {!isPastDeadline && (
                  <ClearAll onClear={handleClearAll} clearing={user ? clearAll.isPending : false} visible={scoringFilled > 0} />
                )}
              </>
            ) : (
              <>
                <div className="h-3 w-40 bg-surface2 animate-pulse mb-3" />
                <SlotsListSkeleton />
              </>
            )}
          </main>

          {loginCta && (
            <div className="fixed bottom-0 left-0 right-0 z-40 bg-bg/95 backdrop-blur border-t border-border px-4 py-2.5 flex justify-center">
              {loginCta}
            </div>
          )}
        </>
      )}

      {!isDesktop && !isPastDeadline && editingSlotKey && cards && (
        <MobilePickerSheet
          slotKey={editingSlotKey}
          cards={cards}
          pickedCards={pickedExcept(editingSlotKey)}
          selectedName={picksBySlot.get(editingSlotKey)}
          onSelect={(name) => selectMobile(editingSlotKey, name)}
          onClose={() => setEditingSlotKey(null)}
        />
      )}
    </div>
  );
}

function P0P1Hero({ cta, innerRef }: { cta: React.ReactNode; innerRef?: React.Ref<HTMLDivElement> }) {
  return (
    <div ref={innerRef} className="sticky top-0 z-30 px-10 py-5 border-b border-border bg-surface flex items-center gap-8">
      <SetGlyph code={SET_CODE} size={84} />
      <div className="shrink-0">
        <SectionLabel size={13}>PACK 0, PICK 1</SectionLabel>
        <div className="flex items-baseline gap-3.5 mt-0.5">
          <span className="font-display tracking-[0.04em]" style={{ fontSize: 56, lineHeight: 0.9 }}>
            {SET_CODE}
          </span>
          <span className="font-display text-[22px] text-muted tracking-[0.06em]">
            {P0P1_SET_NAME.toUpperCase()}
          </span>
        </div>
        <div className="mono text-[11px] mt-1">
          <CountdownInline deadline={VOTING_DEADLINE} size={11} />
        </div>
      </div>
      <div className="flex-1 flex justify-center">
        <p className="text-center text-subtle text-[14px] leading-[1.55]">
          Build a team of 8 cards you think will perform best in {SET_CODE}.
          <br />
          After six weeks, teams are ranked by their total{" "}
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
      </div>
      {cta && <div className="shrink-0">{cta}</div>}
    </div>
  );
}

function MobileIntro({ sets }: { sets: import("../types/leaderboard").SetSummary[] | undefined }) {
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
        Build a team of 8 cards you think will perform best in <span className="font-semibold text-text">{SET_CODE}</span>. After six weeks, teams are ranked by their
        total{" "}
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

function ProgressBar({ filled, total, isComplete }: { filled: number; total: number; isComplete: boolean }) {
  const pct = Math.round((filled / total) * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-surface2 overflow-hidden rounded-full">
        <div
          className={`h-full rounded-full transition-all ${isComplete ? "bg-green" : "bg-green/70"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`mono text-[12px] shrink-0 ${isComplete ? "text-green" : "text-muted"}`}>
        {filled}/{total}
      </span>
    </div>
  );
}

function ClearAll({ onClear, clearing, visible = true }: { onClear: () => void; clearing: boolean; visible?: boolean }) {
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(id);
  }, [confirming]);
  const handleClear = () => {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    setConfirming(false);
    onClear();
  };
  const shown = visible && !clearing;
  return (
    <div className={`flex justify-center mt-1.5 ${shown ? "" : "invisible"}`}>
      <button
        type="button"
        onClick={handleClear}
        disabled={!shown}
        className={`bg-transparent border-0 text-[12px] cursor-pointer transition-colors ${
          confirming ? "text-red font-semibold" : "text-dim hover:text-red"
        }`}
      >
        {confirming ? "Clear all picks?" : "CLEAR ALL PICKS"}
      </button>
    </div>
  );
}

function MobilePickerSheet({
  slotKey,
  cards,
  pickedCards,
  selectedName,
  onSelect,
  onClose,
}: {
  slotKey: SlotKey;
  cards: Card[];
  pickedCards: Set<string>;
  selectedName: string | undefined;
  onSelect: (name: string) => void;
  onClose: () => void;
}) {
  const slot = SLOTS.find((s) => s.key === slotKey)!;
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 bg-bg flex flex-col animate-fadeIn">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
        <SlotPip slotKey={slotKey} size={15} />
        <span className="font-display text-[18px] tracking-[0.06em]">{slot.label}</span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="ml-auto text-muted hover:text-text text-[22px] leading-none bg-transparent border-0 cursor-pointer p-1"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-y-auto themed-scrollbar px-4 py-3">
        <CardSelectionGrid
          slot={slot}
          cards={cards}
          pickedCards={pickedCards}
          selectedName={selectedName}
          onSelect={onSelect}
          minColW={150}
          showLabel={false}
        />
      </div>
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div>
      <div className="flex items-center gap-3 mb-3">
        <div className="h-4 w-32 bg-surface2 animate-pulse" />
        <div className="ml-auto h-7 w-60 bg-surface2 animate-pulse" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="bg-surface2 animate-pulse rounded-lg" style={{ aspectRatio: "488 / 680" }} />
        ))}
      </div>
    </div>
  );
}

const SKEL_LABEL_W = [90, 75, 85, 65, 80, 120, 100, 110, 130];
const SKEL_NAME_W = [120, 100, 110, 95, 105, 130, 115, 125, 140];

function SlotsListSkeleton() {
  return (
    <div className="flex flex-col gap-1.5">
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="w-full flex items-center gap-4 px-4 py-3 bg-surface border border-border2">
          <div className="w-20 h-12 bg-surface2 animate-pulse shrink-0" />
          <div className="flex-1 flex flex-col gap-1.5">
            <div className="h-2 bg-surface2 animate-pulse" style={{ width: SKEL_LABEL_W[i % SKEL_LABEL_W.length] }} />
            <div className="h-3 bg-surface2 animate-pulse" style={{ width: SKEL_NAME_W[i % SKEL_NAME_W.length] }} />
          </div>
        </div>
      ))}
    </div>
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

function CountdownInline({ deadline, size = 14 }: { deadline: Date; size?: number }) {
  const diff = deadline.getTime() - Date.now();
  if (diff <= 0) {
    return <span className="text-muted" style={{ fontSize: size }}>Entries have closed</span>;
  }
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff / (1000 * 60 * 60)) % 24);
  return (
    <span className="whitespace-nowrap" style={{ fontSize: size }}>
      <span className="text-muted">Closes in </span>
      <span className="text-green">{days} days, {hours} hours</span>
    </span>
  );
}
