import { useEffect, useState, type ReactNode } from "react";
import { AppHeader } from "../components/AppHeader";
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
import { PostVotingStats } from "../components/p0p1/PostVotingStats";
import { IncompleteEntryMessage } from "../components/p0p1/IncompleteEntryMessage";
import { useIsMobile } from "../lib/use-is-mobile";
import { useP0P1Ballot } from "../data/useP0P1Ballot";
import { SLOTS } from "../data/p0p1Slots";
import { groupBySlot, findExtremes, classifyYourPick, participantCount } from "../data/p0p1Stats";
import type { Card, P0P1PickStat, SlotDefinition, SlotKey } from "../types/p0p1";

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
    hasParticipated,
    pickStats,
    handleClearAll,
    clearPending,
    setEditingSlotKey,
    activeSlotKey,
    activeSlot,
    selectAdvance,
  } = ballot;
  const isDesktop = !useIsMobile(1024);
  const isCompleteEntrant = isPastDeadline && Boolean(user) && isComplete;
  const isIncompleteEntrant = isPastDeadline && Boolean(user) && !isComplete;

  if (!isDesktop) {
    return <P0P1MobileSelector ballot={ballot} />;
  }

  const loginCta = !authLoading && !user && (
    <button type="button" onClick={signIn} className="bg-transparent border-0 cursor-pointer p-0">
      <CtaPill size="lg" icon={<DiscordIcon size={19} />}>
        {!isPastDeadline ? <>LOG IN TO SUBMIT PICKS</> : <>LOG IN TO VIEW YOUR PICKS</>}
      </CtaPill>
    </button>
  );

  const heroCta = loginCta || (user && !isPastDeadline ? <AutoSaveBadge complete={isComplete} /> : null);

  const entryCount = pickStats ? participantCount(pickStats) : null;

  const belowIntro = isPastDeadline ? (
    entryCount !== null && entryCount > 0 ? (
      <div className="text-subtle text-[14px]">
        {entryCount} player{entryCount !== 1 ? "s" : ""} submitted picks.
      </div>
    ) : null
  ) : (
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
      <P0P1Hero cta={heroCta} belowIntro={belowIntro} isPastDeadline={isPastDeadline} />

      <main className="flex-1 px-10 pb-5 pt-5">
        {(!isPastDeadline || isCompleteEntrant) && (
          <>
            <SectionLabel size={16} className="mb-2 text-white">YOUR PICKS</SectionLabel>
            {dataReady ? (
              <RosterStrip
                activeSlotKey={activeSlotKey}
                picksBySlot={picksBySlot}
                cardsByName={cardsByName}
                locked={isPastDeadline}
                pickStats={hasParticipated ? pickStats : undefined}
                onSelect={(key) => setEditingSlotKey(key)}
              />
            ) : (
              <RosterStripSkeleton />
            )}
          </>
        )}

        {isIncompleteEntrant && (
          <div className="mb-2">
            <IncompleteEntryMessage />
          </div>
        )}

        {isPastDeadline ? (
          pickStats && pickStats.length > 0 && (
            <div className="mt-6">
              <PostVotingStats pickStats={pickStats} cardsByName={cardsByName} picksBySlot={picksBySlot} />
            </div>
          )
        ) : (
          <div className="mt-4">
            {dataReady && cards ? (
              <SlotTransition slotKey={activeSlot.key}>
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
              </SlotTransition>
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

const SLOT_CROSSFADE_MS = 220;

type SlotLayer = { key: string; content: ReactNode };

function SlotTransition({ slotKey, children }: { slotKey: string; children: ReactNode }) {
  const [current, setCurrent] = useState<SlotLayer>({ key: slotKey, content: children });
  const [outgoing, setOutgoing] = useState<SlotLayer | null>(null);

  useEffect(() => {
    if (slotKey === current.key) {
      setCurrent({ key: slotKey, content: children });
      return;
    }
    setOutgoing(current);
    setCurrent({ key: slotKey, content: children });
    const timer = setTimeout(() => setOutgoing(null), SLOT_CROSSFADE_MS);
    return () => clearTimeout(timer);
  }, [slotKey, children, current.key]);

  return (
    <div className="relative">
      <div key={current.key} className="animate-fadeIn">
        {current.content}
      </div>
      {outgoing ? (
        <div key={outgoing.key} className="animate-fadeOut absolute inset-x-0 top-0 pointer-events-none">
          {outgoing.content}
        </div>
      ) : null}
    </div>
  );
}

function RosterStrip({
  activeSlotKey,
  picksBySlot,
  cardsByName,
  locked,
  pickStats,
  onSelect,
}: {
  activeSlotKey: SlotKey;
  picksBySlot: Map<string, string>;
  cardsByName: Map<string, Card>;
  locked: boolean;
  pickStats?: P0P1PickStat[];
  onSelect: (key: SlotKey) => void;
}) {
  const groupedStats = pickStats ? groupBySlot(pickStats) : undefined;

  return (
    <div className="grid grid-cols-8 gap-2">
      {SLOTS.map((slot) => {
        const cardName = picksBySlot.get(slot.key);
        const stat = cardName && groupedStats
          ? groupedStats.get(slot.key)?.find((s) => s.cardName === cardName)
          : undefined;
        const slotStats = groupedStats?.get(slot.key);
        return (
          <RosterTile
            key={slot.key}
            slot={slot}
            card={cardName ? cardsByName.get(cardName) : undefined}
            active={!locked && activeSlotKey === slot.key}
            locked={locked}
            yourStat={stat}
            slotStats={slotStats}
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
  yourStat,
  slotStats,
  onClick,
}: {
  slot: SlotDefinition;
  card: Card | undefined;
  active: boolean;
  locked: boolean;
  yourStat?: P0P1PickStat;
  slotStats?: P0P1PickStat[];
  onClick: () => void;
}) {
  const accent = SLOT_ACCENT[slot.key];
  let classification: ReturnType<typeof classifyYourPick> | undefined;
  if (yourStat && slotStats) {
    const { most, least } = findExtremes(slotStats);
    classification = classifyYourPick(yourStat, most, least);
  }
  const stateColor = classification?.state === "most"
    ? "text-cyan"
    : classification?.state === "rogue"
    ? "text-magenta"
    : "text-white";
  const stripClass = locked
    ? "w-full shrink-0 h-1"
    : `w-full shrink-0 transition-[height] duration-150 ${active ? "h-2" : "h-1 group-hover:h-2"}`;
  const body = (
    <>
      <div className={stripClass} style={{ background: accent }} />
      <div className="relative aspect-square shrink-0 bg-surface2 flex items-center justify-center overflow-hidden">
        {card ? (
          <img src={card.imageArtCrop} alt={card.name} className="w-full h-full object-cover" />
        ) : (
          <SlotPip slotKey={slot.key} size={48} />
        )}
        {classification?.qualifier && (
          <span className={`absolute top-1.5 right-1.5 text-[10px] font-display tracking-wide px-2 py-1 rounded-sm bg-bg/85 ${stateColor}`}>
            {classification.qualifier}
          </span>
        )}
      </div>
      <div className="px-2 pt-2 pb-1.5 shrink-0">
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
      {yourStat && classification && (
        <div className="px-2 pt-2 pb-2.5 shrink-0 border-t border-border2 flex items-baseline gap-1.5">
          <span className={`font-mono tabular-nums text-[22px] leading-none font-semibold`}>
            {yourStat.pickCount}
          </span>
          <span className="text-muted text-[12px] leading-none">
            {yourStat.pickCount === 1 ? (
              <><span className="opacity-60">(you!)</span> picked</>
            ) : (
              "picked"
            )}
          </span>
        </div>
      )}
    </>
  );

  const base = "group relative flex flex-col border border-t-0 overflow-hidden text-left min-w-0";
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
        <div key={i} className="flex flex-col border-t-0 bg-surface border border-border2">
          <div className="h-1 w-full bg-surface2" />
          <div className="aspect-square shrink-0 bg-surface2 animate-pulse" />
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
