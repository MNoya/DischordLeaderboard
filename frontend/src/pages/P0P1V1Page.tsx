import { useEffect, useRef, useState } from "react";
import { AppHeader } from "../components/AppHeader";
import { CtaPill } from "../components/CtaPill";
import { DiscordIcon } from "../components/BrandIcons";
import { SlotCard } from "../components/p0p1/SlotCard";
import { CardSelectionGrid } from "../components/p0p1/CardSelectionGrid";
import { P0P1ProgressBar as ProgressBar } from "../components/p0p1/ProgressBar";
import { ClearAll } from "../components/p0p1/ClearAll";
import { P0P1Hero } from "../components/p0p1/P0P1Hero";
import { P0P1MobileView, SlotsListSkeleton } from "../components/p0p1/P0P1MobileView";
import { useIsMobile } from "../lib/use-is-mobile";
import { useP0P1Ballot } from "../data/useP0P1Ballot";
import { SLOTS } from "../data/p0p1Slots";
import type { SlotKey } from "../types/p0p1";

export function P0P1V1Page() {
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
    activeSlotKey: desktopSlotKey,
    activeSlot: desktopSlot,
    selectAdvance: selectDesktop,
  } = ballot;
  const isDesktop = !useIsMobile(1024);

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

  if (!isDesktop) {
    return <P0P1MobileView ballot={ballot} />;
  }

  const slotCard = (slotKey: SlotKey) => {
    const slot = SLOTS.find((s) => s.key === slotKey)!;
    const cardName = picksBySlot.get(slotKey);
    return (
      <SlotCard
        key={slotKey}
        slot={slot}
        selectedCard={cardName ? cardsByName.get(cardName) : undefined}
        locked={isPastDeadline}
        active={!isPastDeadline && desktopSlotKey === slotKey}
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

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <div ref={navRef}>
        <AppHeader subtitle="P0 P1 Challenge" />
      </div>

      <P0P1Hero cta={loginCta} innerRef={heroRef} />

      <main className="flex-1 flex flex-col px-10 pb-5">
        {!isPastDeadline && (
          <div className="grid gap-6 mt-5" style={{ gridTemplateColumns: "360px minmax(0, 1fr)" }}>
            {dataReady && cards ? (
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
                  <ClearAll onClear={handleClearAll} clearing={clearPending} visible={scoringFilled > 0} />
                </div>
                <CardSelectionGrid
                  key={desktopSlot.key}
                  slot={desktopSlot}
                  cards={cards}
                  pickedCards={pickedExcept(desktopSlot.key)}
                  takenBy={pickedSlotLabels}
                  selectedName={picksBySlot.get(desktopSlot.key)}
                  onSelect={(name) => selectDesktop(desktopSlot.key, name)}
                  minColW={190}
                />
              </>
            ) : (
              <>
                <div>
                  <div className="h-3 w-40 bg-surface2 animate-pulse" />
                  <div className="mt-3">
                    <SlotsListSkeleton />
                  </div>
                </div>
                <CardGridSkeleton />
              </>
            )}
          </div>
        )}

        {cards && isPastDeadline && (
          <div className="mt-5 max-w-[640px] flex flex-col gap-1.5">{SLOTS.map((s) => slotCard(s.key))}</div>
        )}
      </main>
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
