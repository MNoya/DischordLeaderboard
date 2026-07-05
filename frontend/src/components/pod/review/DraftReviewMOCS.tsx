import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { Link } from "react-router-dom";

import { cn } from "../../../lib/utils";
import { Pips } from "../../ManaPips";
import { Tooltip } from "../../Tooltip";
import { ArrowRight, GoSidebarCollapse, TbCards } from "../../Icons";
import { CardImage, CardPreviewProvider, ReviewSetProvider, StackColumn } from "./ReviewCard";
import { cardImageSources } from "../../../data/cardImages";
import { highlightEventLabel } from "../EventLabel";
import { AAvatar } from "../../Brand";
import { DeckScreenshotModal, type DeckLike } from "../DeckScreenshotModal";
import { poolBefore, poolByPack, reconstructDraft, resolveDeck, seatHandle, type DraftPickView } from "../../../data/draft-artifact";
import { cleanPodEventName, stripDiscriminator } from "../../../data/utils";
import type { ArtifactCard, PodDraftArtifact } from "../../../types/leaderboard";

type RevealMode = "revealed" | "click";

const PASS_DIRS = [1, -1, 1];

interface DraftReviewMeta {
  setCode: string;
  name: string;
}

// Per-seat participant data the artifact doesn't carry — drives the final-deck popup. When absent the
// deck button stays hidden.
export interface ReviewSeatInfo {
  seatIndex: number;
  displayName: string;
  participantDisplayName: string;
  avatarUrl: string | null;
  deckColors: string | null;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption: string | null;
  record: string | null;
}

interface DraftReviewMOCSProps {
  artifact: PodDraftArtifact;
  meta: DraftReviewMeta;
  initialSeat?: number;
  initialPack?: number;
  initialPick?: number;
  onClose?: () => void;
  backHref?: string;
  onNavigate?: (seatIndex: number, pack: number, pick: number) => void;
  eventId?: string;
  seatInfo?: ReviewSeatInfo[];
}

export function DraftReviewMOCS({ artifact, meta, initialSeat = 0, initialPack = 0, initialPick = 0, onClose, backHref, onNavigate, eventId, seatInfo }: DraftReviewMOCSProps) {
  const setSymbol = `/set-symbols/${meta.setCode.toLowerCase()}.png`;
  const eventTitle = useMemo(() => cleanPodEventName(meta.name, meta.setCode), [meta]);
  const N = artifact.seats.length;

  const seatInfoMap = useMemo(() => new Map((seatInfo ?? []).map((s) => [s.seatIndex, s])), [seatInfo]);

  const views = useMemo(() => reconstructDraft(artifact), [artifact]);
  const seats = useMemo(
    () =>
      artifact.seats.map((name, i) => {
        const info = seatInfoMap.get(i);
        return {
          index: i,
          name: info ? stripDiscriminator(info.displayName) : seatHandle(name),
          colors: info?.deckColors ?? "",
          avatarUrl: info?.avatarUrl ?? null,
        };
      }),
    [artifact, seatInfoMap],
  );

  const startPack = Math.min(2, Math.max(0, initialPack));
  const startPickSize = views[initialSeat]?.[startPack]?.length ?? 1;
  const startPick = Math.min(startPickSize - 1, Math.max(0, initialPick));
  const [seat, setSeat] = useState(initialSeat);
  const [pack, setPack] = useState(startPack);
  const [pick, setPick] = useState(startPick);
  const [viewMode, setViewMode] = usePersistentState<"step" | "scroll">("draftReviewViewMode", defaultViewMode());
  const [showTable, setShowTable] = usePersistentBool("draftReviewShowTable", false);
  const [deckLayout, setDeckLayout] = usePersistentState<"order" | "columns">("draftReviewDeckLayout", "columns");
  const [revealMode, setRevealMode] = usePersistentState<RevealMode>("draftReviewRevealMode", "revealed");
  const [revealed, setRevealed] = useState(false);
  const [splitSideboard, setSplitSideboard] = usePersistentBool("draftReviewSplitSideboard", false);
  const [deckPopupSeat, setDeckPopupSeat] = useState<number | null>(null);
  const viewportHeight = useViewportHeight();
  const [maxBoosterHeight, setMaxBoosterHeight] = useState(0);
  const reportBoosterHeight = useCallback((h: number) => setMaxBoosterHeight((prev) => (h > prev ? h : prev)), []);
  const deckPanelHeight = deckPanelDefaultHeight(viewportHeight, maxBoosterHeight);

  useEffect(() => {
    const html = document.documentElement;
    html.style.scrollbarGutter = "auto";
    return () => {
      html.style.scrollbarGutter = "";
    };
  }, []);

  const packSize = views[seat][pack].length;
  const totalPicks = views[seat].reduce((sum, p) => sum + p.length, 0);
  const linearIndex = views[seat].slice(0, pack).reduce((sum, p) => sum + p.length, 0) + pick;

  const pickShown = revealMode === "revealed" || revealed;
  const awaitingReveal = revealMode === "click" && !revealed;

  const onNavigateRef = useRef(onNavigate);
  onNavigateRef.current = onNavigate;
  const lastNavSig = useRef(`${initialSeat}/${startPack}/${startPick}`);
  useEffect(() => {
    const sig = `${seat}/${pack}/${pick}`;
    if (sig === lastNavSig.current) {
      return;
    }
    lastNavSig.current = sig;
    onNavigateRef.current?.(seat, pack, pick);
  }, [seat, pack, pick]);

  const goTo = (nextPack: number, nextPick: number) => {
    setPack(nextPack);
    setPick(nextPick);
    setRevealed(false);
  };
  const handlePrev = () => {
    if (pick > 0) {
      goTo(pack, pick - 1);
    } else if (pack > 0) {
      goTo(pack - 1, views[seat][pack - 1].length - 1);
    }
  };
  const handleNext = () => {
    const next = nextCoord(views, seat, pack, pick);
    if (next) {
      goTo(next.pack, next.pick);
    }
  };
  const changeReveal = (m: RevealMode) => {
    setRevealMode(m);
    setRevealed(false);
  };
  const changeSeat = (i: number) => {
    if (linearIndex === totalPicks - 1) {
      setPack(0);
      setPick(0);
    }
    setSeat(i);
    setRevealed(false);
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (deckPopupSeat != null || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) {
        return;
      }
      const t = e.target;
      if (t instanceof HTMLElement && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) {
        return;
      }
      const navKey = e.key === "ArrowLeft" || e.key === "ArrowRight" || e.key === " ";
      if (navKey && document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        handlePrev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        if (awaitingReveal) {
          setRevealed(true);
        } else {
          handleNext();
        }
      } else if (e.key === " ") {
        e.preventDefault();
        changeReveal(revealMode === "revealed" ? "click" : "revealed");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handlePrev, handleNext, awaitingReveal, changeReveal, revealMode, deckPopupSeat]);

  useEffect(() => {
    const next = nextCoord(views, seat, pack, pick);
    if (!next) {
      return;
    }
    for (const idx of views[seat][next.pack][next.pick].booster) {
      const card = artifact.cards[idx];
      const url = cardImageSources(card.n, card.s ?? artifact.set)[0];
      if (url) {
        new Image().src = url;
      }
    }
  }, [views, seat, pack, pick, artifact]);

  const view = views[seat][pack][pick];
  const boosterCards = view.booster.map((idx) => artifact.cards[idx]);
  const active = seats[seat];

  const deck = artifact.decks?.[seat];
  const sideSet = useMemo(() => new Set(deck?.side ?? []), [deck]);
  const hasSideboard = (deck?.side?.length ?? 0) > 0;

  const toCards = (indices: number[]) => indices.map((idx) => artifact.cards[idx]);
  const poolIdx = poolBefore(views, seat, pack, pick);
  const poolRowsIdx = poolByPack(views, seat, pack, pick);
  const pool = toCards(hasSideboard ? poolIdx.filter((idx) => !sideSet.has(idx)) : poolIdx);
  const poolRows = (hasSideboard ? poolRowsIdx.map((row) => row.filter((idx) => !sideSet.has(idx))) : poolRowsIdx).map(toCards);
  const sideboardCards = hasSideboard ? toCards(poolIdx.filter((idx) => sideSet.has(idx))) : [];
  const lastPickIdx = poolIdx.length > 0 ? poolIdx[poolIdx.length - 1] : null;
  const lastInSideboard = hasSideboard && lastPickIdx != null && sideSet.has(lastPickIdx);

  const activeInfo = seatInfoMap.get(seat);
  const canOpenDeck = !!activeInfo && (activeInfo.deckScreenshotUrl != null || (deck?.main.length ?? 0) > 0);
  const deckPopup = deckPopupSeat == null ? null : buildDeckLike(deckPopupSeat);

  function buildDeckLike(s: number): DeckLike | null {
    const info = seatInfoMap.get(s);
    if (!info) {
      return null;
    }
    return {
      eventId,
      displayName: info.displayName,
      participantDisplayName: info.participantDisplayName,
      deckColors: info.deckColors,
      deckScreenshotUrl: info.deckScreenshotUrl,
      deckScreenshotCaption: info.deckScreenshotCaption,
      mainboard: resolveDeck(artifact, s),
      record: info.record,
    };
  }

  const left = (seat - 1 + N) % N;
  const right = (seat + 1) % N;
  const dir = PASS_DIRS[pack];

  const pileFor = (seatIndex: number): Pile => {
    const indices = poolBefore(views, seatIndex, pack, pick);
    const side = new Set(artifact.decks?.[seatIndex]?.side ?? []);
    const main = toCards(indices.filter((i) => !side.has(i)));
    const board = toCards(indices.filter((i) => side.has(i)));
    const lastInSide = indices.length > 0 && side.has(indices[indices.length - 1]);
    return { main, board, lastInSide };
  };
  const leftPile = pileFor(left);
  const centerPile = pileFor(seat);
  const rightPile = pileFor(right);

  return (
    <ReviewSetProvider value={artifact.set}>
    <CardPreviewProvider setCode={meta.setCode}>
    <div className="fixed inset-0 z-50 flex select-none flex-col bg-bg text-text">
      <MobileTopBar
        setSymbol={setSymbol}
        eventTitle={eventTitle}
        left={seats[left]}
        active={active}
        right={seats[right]}
        passRight={dir === 1}
        onSelectLeft={() => changeSeat(left)}
        onSelectRight={() => changeSeat(right)}
        onClose={onClose}
        backHref={backHref}
        scrollOn={viewMode === "scroll"}
        onToggleScroll={() => setViewMode(viewMode === "scroll" ? "step" : "scroll")}
      />
      <Header
        setSymbol={setSymbol}
        eventTitle={eventTitle}
        onClose={onClose}
        backHref={backHref}
        pack={pack}
        pick={pick}
        packSize={packSize}
        onJump={goTo}
        onPrev={handlePrev}
        onNext={handleNext}
        atStart={linearIndex === 0}
        atEnd={linearIndex === totalPicks - 1}
        awaitingReveal={awaitingReveal}
        onReveal={() => setRevealed(true)}
        revealMode={revealMode}
        onRevealMode={changeReveal}
        showTable={showTable}
        onToggleTable={() => setShowTable((v) => !v)}
        viewMode={viewMode}
        onViewMode={setViewMode}
      />
      <div className="relative flex min-h-0 flex-1">
        <section className="relative flex min-w-0 flex-1 flex-col">
          {viewMode === "scroll" ? (
            <>
              <div className="absolute right-2 top-1 z-20 lg:hidden">
                <MobileToggle
                  label="SHOW PICKS"
                  ariaLabel="Show picks"
                  on={revealMode === "revealed"}
                  onToggle={() => changeReveal(revealMode === "revealed" ? "click" : "revealed")}
                />
              </div>
              <DraftScrollRecap
                packs={views[seat]}
                cards={artifact.cards}
                revealMode={revealMode}
                initialPack={pack}
                initialPick={pick}
                onActivePick={(p, k) => {
                  setPack(p);
                  setPick(k);
                }}
              />
            </>
          ) : (
            <>
              <BoosterPanel
                cards={boosterCards}
                pickedPos={pickShown ? view.takenPos : null}
                fadeKey={`${seat}-${pack}-${pick}`}
                onNaturalHeight={reportBoosterHeight}
              />
              <MobileNavDivider
                pack={pack}
                pick={pick}
                onJump={goTo}
                onPrev={handlePrev}
                onNext={handleNext}
                atStart={linearIndex === 0}
                atEnd={linearIndex === totalPicks - 1}
                awaitingReveal={awaitingReveal}
                onReveal={() => setRevealed(true)}
                revealMode={revealMode}
                onRevealMode={changeReveal}
              />
              <PoolBar
                cards={pool}
                rows={poolRows}
                sideboard={sideboardCards}
                lastInSideboard={lastInSideboard}
                deckLayout={deckLayout}
                onToggleDeckLayout={() => setDeckLayout((l) => (l === "order" ? "columns" : "order"))}
                canSplit={hasSideboard}
                splitSideboard={splitSideboard}
                onToggleSplit={() => setSplitSideboard((v) => !v)}
                onOpenDeck={canOpenDeck ? () => setDeckPopupSeat(seat) : undefined}
              />
            </>
          )}
        </section>
        <aside
          className={cn(
            "relative hidden shrink-0 overflow-hidden bg-surface/40 transition-[width] duration-200 lg:block",
            showTable ? "w-[300px] border-l border-border" : "w-0",
          )}
        >
          <div className="h-full w-[300px]">
            <PlayerGrid
              seats={seats}
              activeSeat={seat}
              onSelect={changeSeat}
              passRight={dir === 1}
            />
          </div>
        </aside>
      </div>
      {viewMode === "step" && (
        <BottomPanel
          defaultHeight={deckPanelHeight}
          activeName={active.name}
          activeAvatarUrl={active.avatarUrl}
          cards={pool}
          rows={poolRows}
          sideboard={sideboardCards}
          lastInSideboard={lastInSideboard}
          deckLayout={deckLayout}
          onToggleDeckLayout={() => setDeckLayout((l) => (l === "order" ? "columns" : "order"))}
          canSplit={hasSideboard}
          splitSideboard={splitSideboard}
          onToggleSplit={() => setSplitSideboard((v) => !v)}
          onOpenDeck={canOpenDeck ? () => setDeckPopupSeat(seat) : undefined}
          left={seats[left]}
          right={seats[right]}
          passRight={dir === 1}
          leftPile={leftPile}
          centerPile={centerPile}
          rightPile={rightPile}
        />
      )}
      {deckPopup && (
        <DeckScreenshotModal
          participant={deckPopup}
          hideDraftLog
          onClose={() => setDeckPopupSeat(null)}
          onPrev={() => setDeckPopupSeat((s) => (s == null ? s : (s - 1 + N) % N))}
          onNext={() => setDeckPopupSeat((s) => (s == null ? s : (s + 1) % N))}
        />
      )}
    </div>
    </CardPreviewProvider>
    </ReviewSetProvider>
  );
}

function nextCoord(views: DraftPickView[][][], seat: number, pack: number, pick: number): { pack: number; pick: number } | null {
  if (pick + 1 < views[seat][pack].length) {
    return { pack, pick: pick + 1 };
  }
  if (pack < 2) {
    return { pack: pack + 1, pick: 0 };
  }
  return null;
}

const DESKTOP_MIN_WIDTH = 1024;

function defaultViewMode(): "step" | "scroll" {
  if (typeof window === "undefined") {
    return "step";
  }
  return window.innerWidth < DESKTOP_MIN_WIDTH ? "scroll" : "step";
}

function usePersistentState<T extends string>(key: string, fallback: T): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === "undefined") {
      return fallback;
    }
    return (window.localStorage.getItem(key) as T | null) ?? fallback;
  });
  useEffect(() => {
    window.localStorage.setItem(key, value);
  }, [key, value]);
  return [value, setValue];
}

function usePersistentBool(key: string, fallback: boolean): [boolean, Dispatch<SetStateAction<boolean>>] {
  const [value, setValue] = useState<boolean>(() => {
    if (typeof window === "undefined") {
      return fallback;
    }
    const stored = window.localStorage.getItem(key);
    return stored == null ? fallback : stored === "1";
  });
  useEffect(() => {
    window.localStorage.setItem(key, value ? "1" : "0");
  }, [key, value]);
  return [value, setValue];
}

interface Seat {
  index: number;
  name: string;
  colors: string;
  avatarUrl: string | null;
}

interface Pile {
  main: ArtifactCard[];
  board: ArtifactCard[];
  lastInSide: boolean;
}

// Mobile-only slim bar: the left and right neighbors stay anchored to their physical sides; the arrow
// between them points the way cards pass and flips for the right-to-left packs. Tapping a neighbor
// switches seats so you can walk the table.
function MobileTopBar({
  setSymbol,
  eventTitle,
  left,
  active,
  right,
  passRight,
  onSelectLeft,
  onSelectRight,
  onClose,
  backHref,
  scrollOn,
  onToggleScroll,
}: {
  setSymbol: string;
  eventTitle: string;
  left: Seat;
  active: Seat;
  right: Seat;
  passRight: boolean;
  onSelectLeft: () => void;
  onSelectRight: () => void;
  onClose?: () => void;
  backHref?: string;
  scrollOn: boolean;
  onToggleScroll: () => void;
}) {
  const arrow = passRight ? "»" : "«";
  const name = "truncate font-display text-[13px] tracking-[0.04em] text-subtle [-webkit-tap-highlight-color:transparent] active:text-text";
  const backClass = "flex shrink-0 items-center gap-1 text-subtle [-webkit-tap-highlight-color:transparent] active:text-text";
  const backContent = (
    <>
      <ChevronIcon dir="left" />
      <img src={setSymbol} alt="" className="h-5 w-5" />
      <span className="max-w-[84px] truncate font-display text-[13px] tracking-[0.04em]">
        {highlightEventLabel(eventTitle)}
      </span>
    </>
  );
  return (
    <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border bg-surface px-2 lg:hidden">
      {backHref ? (
        <Link to={backHref} aria-label="Back to pod" className={backClass}>
          {backContent}
        </Link>
      ) : (
        <button onClick={onClose} aria-label="Back to pod" className={backClass}>
          {backContent}
        </button>
      )}
      <div className="flex min-w-0 flex-1 items-center justify-center gap-1.5">
        <button onClick={onSelectLeft} className={cn(name, "max-w-[78px]")}>
          {left.name}
        </button>
        <span className="shrink-0 font-mono text-[13px] text-subtle">{arrow}</span>
        <span className="max-w-[96px] shrink truncate text-center font-display text-[15px] tracking-[0.06em] text-green">
          {active.name}
        </span>
        <span className="shrink-0 font-mono text-[13px] text-subtle">{arrow}</span>
        <button onClick={onSelectRight} className={cn(name, "max-w-[78px]")}>
          {right.name}
        </button>
      </div>
      <MobileToggle label="SCROLL" ariaLabel="Scroll the whole draft" on={scrollOn} onToggle={onToggleScroll} />
    </div>
  );
}

function MobileToggle({ label, on, onToggle, ariaLabel }: { label: string; on: boolean; onToggle: () => void; ariaLabel: string }) {
  return (
    <button
      onClick={onToggle}
      role="switch"
      aria-checked={on}
      aria-label={ariaLabel}
      className="flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-border bg-surface2 px-2 [-webkit-tap-highlight-color:transparent] active:bg-white/10"
    >
      <span className={cn("font-display text-[10px] tracking-[0.1em]", on ? "text-green" : "text-subtle")}>{label}</span>
      <span className={cn("relative h-3.5 w-6 rounded-full transition-colors", on ? "bg-green" : "bg-border2")}>
        <span className={cn("absolute top-[2px] h-2.5 w-2.5 rounded-full bg-white transition-all", on ? "left-[11px]" : "left-[2px]")} />
      </span>
    </button>
  );
}

function Header({
  setSymbol,
  eventTitle,
  onClose,
  backHref,
  pack,
  pick,
  packSize,
  onJump,
  onPrev,
  onNext,
  atStart,
  atEnd,
  awaitingReveal,
  onReveal,
  revealMode,
  onRevealMode,
  showTable,
  onToggleTable,
  viewMode,
  onViewMode,
}: {
  setSymbol: string;
  eventTitle: string;
  onClose?: () => void;
  backHref?: string;
  pack: number;
  pick: number;
  packSize: number;
  onJump: (pack: number, pick: number) => void;
  onPrev: () => void;
  onNext: () => void;
  atStart: boolean;
  atEnd: boolean;
  awaitingReveal: boolean;
  onReveal: () => void;
  revealMode: RevealMode;
  onRevealMode: (m: RevealMode) => void;
  showTable: boolean;
  onToggleTable: () => void;
  viewMode: "step" | "scroll";
  onViewMode: (m: "step" | "scroll") => void;
}) {
  const revealControl = awaitingReveal ? (
    <Tooltip label="Reveal picked card" side="bottom">
      <button
        onClick={onReveal}
        aria-label="Reveal picked card"
        className="flex h-9 min-w-[84px] items-center justify-center gap-1.5 rounded-md border border-white/40 bg-surface2 px-3 font-display text-[13px] tracking-[0.12em] text-text transition-[transform,background-color,border-color,color] duration-150 ease-out touch-manipulation [-webkit-tap-highlight-color:transparent] hover:border-white/60 hover:bg-white/10 active:scale-90 active:bg-white/20 motion-reduce:active:scale-100"
      >
        REVEAL
        <EyeIcon off={false} />
      </button>
    </Tooltip>
  ) : (
    <NavArrow dir="next" onClick={onNext} disabled={atEnd} />
  );

  const showPicksToggle = (
    <ShowPicksToggle
      showPicks={revealMode === "revealed"}
      onToggle={() => onRevealMode(revealMode === "revealed" ? "click" : "revealed")}
    />
  );

  return (
    <header className="hidden h-[60px] shrink-0 items-center gap-5 border-b border-border bg-surface px-5 lg:flex">
      {backHref ? (
        <Link
          to={backHref}
          className="flex min-w-0 flex-1 items-center gap-2.5 text-left transition-colors hover:text-green"
          aria-label="Back to pod"
        >
          <ChevronIcon dir="left" />
          <img src={setSymbol} alt="" className="h-7 w-7 shrink-0" />
          <span className="truncate font-display text-[19px] tracking-[0.08em]">
            {highlightEventLabel(eventTitle)}
          </span>
        </Link>
      ) : (
        <button
          onClick={onClose}
          className="flex min-w-0 flex-1 items-center gap-2.5 text-left transition-colors hover:text-green"
          aria-label="Back to pod"
        >
          <ChevronIcon dir="left" />
          <img src={setSymbol} alt="" className="h-7 w-7 shrink-0" />
          <span className="truncate font-display text-[19px] tracking-[0.08em]">
            {highlightEventLabel(eventTitle)}
          </span>
        </button>
      )}

      {viewMode === "step" && (
        <div className="flex items-center gap-5">
          <ChipRow label="PACK">
            {[0, 1, 2].map((p) => (
              <Chip key={p} active={p === pack} onClick={() => onJump(p, 0)}>
                {p + 1}
              </Chip>
            ))}
          </ChipRow>
          <ChipRow label="PICK">
            {Array.from({ length: packSize }, (_, k) => (
              <Chip key={k} active={k === pick} onClick={() => onJump(pack, k)}>
                {k + 1}
              </Chip>
            ))}
          </ChipRow>
          <div className="flex items-center gap-2">
            <NavArrow dir="prev" onClick={onPrev} disabled={atStart} />
            {revealControl}
          </div>
        </div>
      )}

      <div className="flex flex-1 items-center justify-end gap-2">
        {showPicksToggle}
        <ScrollToggle on={viewMode === "scroll"} onToggle={() => onViewMode(viewMode === "scroll" ? "step" : "scroll")} />
        <SwitchToggle
          label="TABLE"
          on={showTable}
          onToggle={onToggleTable}
          ariaLabel="Show table"
          tooltip={showTable ? "Hide table" : "Show table"}
        />
        <button
          onClick={onClose}
          aria-label="Close"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface2 text-muted transition-colors hover:border-white/40 hover:bg-white/10 hover:text-text"
        >
          ✕
        </button>
      </div>
    </header>
  );
}

function SwitchToggle({
  label,
  on,
  onToggle,
  tooltip,
  ariaLabel,
  block = false,
  disabled = false,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  tooltip: string;
  ariaLabel: string;
  block?: boolean;
  disabled?: boolean;
}) {
  const [hover, setHover] = useState(false);
  return (
    <Tooltip label={tooltip} side={block ? "left" : "bottom"} open={hover && !disabled}>
      <button
        onClick={onToggle}
        onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
        onPointerLeave={() => setHover(false)}
        disabled={disabled}
        role="switch"
        aria-checked={on}
        aria-label={ariaLabel}
        className={cn(
          "flex h-9 items-center gap-2 rounded-md border border-border bg-surface2 px-2.5 transition-colors [-webkit-tap-highlight-color:transparent]",
          disabled ? "cursor-not-allowed opacity-40" : "hover:border-white/40 hover:bg-white/10",
          block ? "w-full justify-between" : "shrink-0",
        )}
      >
        <span className={cn("font-display text-[12px] tracking-[0.12em]", on ? "text-green" : "text-subtle")}>
          {label}
        </span>
        <span className={cn("relative h-[18px] w-8 rounded-full transition-colors", on ? "bg-green" : "bg-border2")}>
          <span
            className={cn(
              "absolute top-[3px] h-3.5 w-3.5 rounded-full bg-white transition-all",
              on ? "left-[15px]" : "left-[1px]",
            )}
          />
        </span>
      </button>
    </Tooltip>
  );
}

function ShowPicksToggle({ showPicks, onToggle, block = false }: { showPicks: boolean; onToggle: () => void; block?: boolean }) {
  return (
    <SwitchToggle
      label="SHOW PICKS"
      on={showPicks}
      onToggle={onToggle}
      ariaLabel="Show picks"
      tooltip={showPicks ? "Hide picks to guess before revealing (Space)" : "Reveal picks automatically (Space)"}
      block={block}
    />
  );
}

function ShowNeighborsToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <SwitchToggle
      label="SHOW NEIGHBORS"
      on={on}
      onToggle={onToggle}
      ariaLabel="Show neighbors"
      tooltip={on ? "Hide Left & Right players" : "Show Left & Right players"}
    />
  );
}

function ScrollToggle({ on, onToggle, block = false }: { on: boolean; onToggle: () => void; block?: boolean }) {
  return (
    <SwitchToggle
      label="SCROLL MODE"
      on={on}
      onToggle={onToggle}
      ariaLabel="Scroll the whole draft"
      tooltip={on ? "Whole draft in one scrollable view" : "One pick at a time"}
      block={block}
    />
  );
}

function ChipRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-display text-[14px] tracking-[0.18em] text-subtle">{label}</span>
      <div className="flex gap-1">{children}</div>
    </div>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex h-8 min-w-[32px] items-center justify-center rounded border px-2 font-display text-[16px] tracking-[0.04em] tabular-nums transition-colors",
        active
          ? "border-green/60 bg-green/15 text-green"
          : "border-border bg-surface2 text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text",
      )}
    >
      {children}
    </button>
  );
}

const BOOSTER_GAP = 8;
const BOOSTER_PAD = 12;

function BoosterPanel({
  cards,
  pickedPos,
  fadeKey,
  onNaturalHeight,
}: {
  cards: ArtifactCard[];
  pickedPos: number | null;
  fadeKey: string;
  onNaturalHeight?: (height: number) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const content = scrollRef.current?.firstElementChild as HTMLElement | null | undefined;
    if (!content || !onNaturalHeight) {
      return;
    }
    const measure = () => onNaturalHeight(content.offsetHeight + BOOSTER_PAD * 2);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(content);
    return () => observer.disconnect();
  }, [cards, onNaturalHeight]);
  return (
    <div ref={scrollRef} className="themed-scrollbar min-h-0 flex-1 overflow-y-auto" style={{ padding: BOOSTER_PAD }}>
      <div key={fadeKey} className="animate-fadeUpIn">
        <BoosterGrid cards={cards} pickedPos={pickedPos} />
      </div>
    </div>
  );
}

function BoosterGrid({ cards, pickedPos }: { cards: ArtifactCard[]; pickedPos: number | null }) {
  return (
    <div className="flex flex-wrap content-start justify-center" style={{ gap: BOOSTER_GAP }}>
      {cards.map((card, i) => (
        <div key={i} className="w-[calc((100%-16px)/3)] sm:w-[calc((100%-24px)/4)] lg:w-[210px]">
          <BoosterCard card={card} picked={i === pickedPos} />
        </div>
      ))}
    </div>
  );
}

function BoosterCard({ card, picked }: { card: ArtifactCard; picked: boolean }) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)] transition-transform duration-150 hover:z-10 hover:scale-[1.04]",
        picked && "p0p1-card-selected z-10 scale-[1.03] hover:scale-[1.05]",
      )}
    >
      <CardImage card={card} />
    </div>
  );
}

// Continuous-scroll recap: every pick across all three packs stacked top-to-bottom for one seat, each
// section showing that pick's booster with the taken card highlighted. No deck/pool state, just the
// sequence — a fast skim. Honors the reveal mode: "click" hides each pick until its REVEAL is tapped.
function DraftScrollRecap({
  packs,
  cards,
  revealMode,
  initialPack,
  initialPick,
  onActivePick,
}: {
  packs: DraftPickView[][];
  cards: ArtifactCard[];
  revealMode: RevealMode;
  initialPack: number;
  initialPick: number;
  onActivePick: (pack: number, pick: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const onActivePickRef = useRef(onActivePick);
  onActivePickRef.current = onActivePick;
  useLayoutEffect(() => {
    const target = ref.current?.querySelector(`[data-pick="${initialPack}-${initialPick}"]`);
    if (target instanceof HTMLElement) {
      target.scrollIntoView({ block: "start" });
    }
  }, []);
  useEffect(() => {
    const root = ref.current;
    if (!root) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        let topmost: IntersectionObserverEntry | null = null;
        for (const entry of entries) {
          if (entry.isIntersecting && (!topmost || entry.boundingClientRect.top < topmost.boundingClientRect.top)) {
            topmost = entry;
          }
        }
        const key = topmost && (topmost.target as HTMLElement).dataset.pick;
        if (!key) {
          return;
        }
        const [p, k] = key.split("-").map(Number);
        onActivePickRef.current(p, k);
      },
      { root, rootMargin: "0px 0px -85% 0px", threshold: 0 },
    );
    root.querySelectorAll("[data-pick]").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={ref} className="themed-scrollbar min-h-0 flex-1 overflow-y-auto px-3 pb-3 pt-1 lg:px-8 lg:py-6">
      {packs.map((pickViews, p) =>
        pickViews.map((view, k) => (
          <RecapSection key={`${p}-${k}`} pack={p} pick={k} view={view} cards={cards} revealMode={revealMode} />
        )),
      )}
    </div>
  );
}

function RecapSection({
  pack,
  pick,
  view,
  cards,
  revealMode,
}: {
  pack: number;
  pick: number;
  view: DraftPickView;
  cards: ArtifactCard[];
  revealMode: RevealMode;
}) {
  const [clicked, setClicked] = useState(false);
  const shown = revealMode === "revealed" || clicked;
  const boosterCards = view.booster.map((idx) => cards[idx]);
  const takenName = boosterCards[view.takenPos]?.n ?? "";
  return (
    <section data-pick={`${pack}-${pick}`} className="mb-7 scroll-mt-3 lg:mb-9">
      <div className="mb-2 flex h-9 items-center gap-3 border-b border-border lg:mb-3 lg:h-10">
        <span className="font-display text-[15px] tracking-[0.16em] text-subtle">PACK {pack + 1}</span>
        <span className="font-display text-[15px] tracking-[0.16em] text-subtle">PICK {pick + 1}</span>
        {shown ? (
          <span className="flex min-w-0 items-center gap-2">
            <ArrowRight size={16} className="shrink-0 text-subtle" aria-hidden="true" />
            <span className="truncate font-display text-[16px] tracking-[0.04em] text-green">{takenName}</span>
          </span>
        ) : (
          <button
            onClick={() => setClicked(true)}
            className="ml-1 rounded border border-border bg-surface2 px-2.5 py-1 font-display text-[12px] tracking-[0.12em] text-subtle transition-colors hover:border-white/40 hover:text-text"
          >
            REVEAL
          </button>
        )}
      </div>
      <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(104px,1fr))] lg:[grid-template-columns:repeat(auto-fill,minmax(148px,1fr))]">
        {boosterCards.map((card, i) => (
          <BoosterCard key={i} card={card} picked={shown && i === view.takenPos} />
        ))}
      </div>
    </section>
  );
}

const PANEL_DRAG_THRESHOLD = 4;
const PANEL_MIN_HEIGHT = 64;
const PANEL_COLLAPSE_AT = 40;

function useResizableHeight(baseHeight: number, onCollapse?: () => void) {
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const height = dragHeight ?? baseHeight;
  const beginResize = (startY: number, fromHeight?: number) => {
    const startHeight = fromHeight ?? dragHeight ?? baseHeight;
    let collapsible = fromHeight == null;
    if (fromHeight != null) {
      setDragHeight(fromHeight);
    }
    setDragging(true);
    const onMove = (ev: PointerEvent) => {
      const next = startHeight - (ev.clientY - startY);
      if (next >= PANEL_MIN_HEIGHT) {
        collapsible = true;
      }
      if (onCollapse && collapsible && next < PANEL_COLLAPSE_AT) {
        onCollapse();
        setDragHeight(null);
        cleanup();
        return;
      }
      const floor = collapsible ? PANEL_MIN_HEIGHT : 0;
      setDragHeight(Math.min(window.innerHeight * 0.72, Math.max(floor, next)));
    };
    const onUp = () => cleanup();
    function cleanup() {
      setDragging(false);
      setDragHeight((h) => (h != null && h < PANEL_MIN_HEIGHT ? PANEL_MIN_HEIGHT : h));
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };
  return { height, beginResize, dragging };
}

// Thick bar shared by the deck pool and the neighbor band: a tap toggles the panel collapsed, a press
// and drag past a small threshold resizes it instead. The chevron tab on the top edge shows which way
// a tap moves it. With nothing to show (no neighbor picks yet) it renders static, no toggle or resize.
function PanelBar({
  open,
  canCollapse,
  onToggle,
  onResizeStart,
  children,
}: {
  open: boolean;
  canCollapse: boolean;
  onToggle: () => void;
  onResizeStart: (startY: number, fromHeight?: number) => void;
  children: React.ReactNode;
}) {
  const handlePointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) {
      return;
    }
    e.preventDefault();
    const startY = e.clientY;
    let dragging = false;
    const onMove = (ev: PointerEvent) => {
      if (!dragging && Math.abs(ev.clientY - startY) > PANEL_DRAG_THRESHOLD) {
        dragging = true;
        if (open) {
          onResizeStart(startY);
        } else {
          onToggle();
          onResizeStart(startY, 0);
        }
      }
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      if (!dragging) {
        onToggle();
      }
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };
  if (!canCollapse) {
    return (
      <div className="relative hidden h-10 w-full shrink-0 items-center border-t border-border bg-bg lg:flex">
        {children}
      </div>
    );
  }
  return (
    <div
      onPointerDown={handlePointerDown}
      className="group relative hidden h-10 w-full shrink-0 cursor-row-resize select-none items-center border-t border-border bg-bg transition-colors hover:bg-surface2 lg:flex"
    >
      <span className="absolute bottom-full left-1/2 flex -translate-x-1/2 translate-y-px items-center justify-center rounded-t-md border border-b-0 border-border bg-bg px-3 text-subtle transition-colors group-hover:bg-surface2 group-hover:text-text">
        <ChevronIcon dir={open ? "down" : "up"} />
      </span>
      {children}
    </div>
  );
}

function DeckBarStat({ n, label }: { n: number; label: string }) {
  if (n === 0) {
    return null;
  }
  return (
    <span className="flex items-baseline gap-1">
      <span className="tabular-nums text-subtle">{n}</span>
      <span className="text-[12px] tracking-[0.1em] text-muted">{label}</span>
    </span>
  );
}

// Mobile deck pool: always visible below the booster, no collapse. Desktop deck+neighbors live in
// BottomPanel instead.
function PoolBar({
  cards,
  rows,
  sideboard,
  lastInSideboard,
  deckLayout,
  onToggleDeckLayout,
  canSplit,
  splitSideboard,
  onToggleSplit,
  onOpenDeck,
}: {
  cards: ArtifactCard[];
  rows: ArtifactCard[][];
  sideboard: ArtifactCard[];
  lastInSideboard: boolean;
  deckLayout: "order" | "columns";
  onToggleDeckLayout: () => void;
  canSplit: boolean;
  splitSideboard: boolean;
  onToggleSplit: () => void;
  onOpenDeck?: () => void;
}) {
  const order = deckLayout === "order";
  return (
    <div className="relative shrink-0 border-t border-border bg-surface/60 pb-1 pl-0 pr-1 pt-0 lg:hidden">
      <div className="absolute bottom-2 right-2 z-20">
        <PoolControls
          canSplit={canSplit}
          splitSideboard={splitSideboard}
          onToggleSplit={onToggleSplit}
          onOpenDeck={onOpenDeck}
          deckLayout={deckLayout}
          onToggleDeckLayout={onToggleDeckLayout}
        />
      </div>
      <div className={cn("flex gap-1", order ? "h-[24dvh]" : "h-[32dvh]")}>
        <PoolCards
          order={order}
          rows={rows}
          cards={cards}
          lastInSideboard={lastInSideboard}
          splitSideboard={splitSideboard}
          sideboard={sideboard}
          cardWidth={104}
          reveal={order ? 21 : 16}
          sideReveal={14}
          poolAlign="right"
        />
      </div>
    </div>
  );
}

function PoolCards({
  order,
  rows,
  cards,
  lastInSideboard,
  splitSideboard,
  sideboard,
  cardWidth,
  reveal,
  sideReveal,
  groupByType = false,
  poolAlign,
}: {
  order: boolean;
  rows: ArtifactCard[][];
  cards: ArtifactCard[];
  lastInSideboard: boolean;
  splitSideboard: boolean;
  sideboard: ArtifactCard[];
  cardWidth: number;
  reveal: number;
  sideReveal: number;
  groupByType?: boolean;
  poolAlign?: "left" | "right";
}) {
  const showPane = splitSideboard && sideboard.length > 0;
  const inlineSideboard = showPane ? [] : sideboard;
  return (
    <>
      <div className="relative min-w-0 flex-1">
        {order ? (
          <OrderStrip rows={rows} sideboard={inlineSideboard} lastPickInSideboard={lastInSideboard} markLast cardWidth={cardWidth} reveal={reveal} />
        ) : (
          <Pool cards={cards} sideboard={inlineSideboard} lastPickInSideboard={lastInSideboard} groupByType={groupByType} align={poolAlign} markLast cardWidth={cardWidth} reveal={reveal} />
        )}
      </div>
      {showPane && (
        <SideboardPane cards={sideboard} markLast={lastInSideboard} cardWidth={Math.round(cardWidth * 0.9)} reveal={sideReveal} />
      )}
    </>
  );
}

// Desktop bottom zone: one bar identifying the active player, its DECK|NEIGHBORS switch, and a single
// collapsible/resizable panel that shows either the player's own pool or the two neighbors' pools.
function BottomPanel({
  defaultHeight,
  activeName,
  activeAvatarUrl,
  cards,
  rows,
  sideboard,
  lastInSideboard,
  deckLayout,
  onToggleDeckLayout,
  canSplit,
  splitSideboard,
  onToggleSplit,
  onOpenDeck,
  left,
  right,
  passRight,
  leftPile,
  centerPile,
  rightPile,
}: {
  defaultHeight: number;
  activeName: string;
  activeAvatarUrl: string | null;
  cards: ArtifactCard[];
  rows: ArtifactCard[][];
  sideboard: ArtifactCard[];
  lastInSideboard: boolean;
  deckLayout: "order" | "columns";
  onToggleDeckLayout: () => void;
  canSplit: boolean;
  splitSideboard: boolean;
  onToggleSplit: () => void;
  onOpenDeck?: () => void;
  left: Seat;
  right: Seat;
  passRight: boolean;
  leftPile: Pile;
  centerPile: Pile;
  rightPile: Pile;
}) {
  const [open, setOpen] = useState(true);
  const [tab, setTab] = useState<"deck" | "neighbors">("deck");
  const order = deckLayout === "order";
  const showSideboard = splitSideboard && sideboard.length > 0;
  const { height, beginResize, dragging } = useResizableHeight(defaultHeight, () => setOpen(false));

  const activeTab = tab;
  let creatures = 0;
  let lands = 0;
  for (const card of cards) {
    const type = card.type ?? "";
    if (/creature/i.test(type)) {
      creatures++;
    } else if (/land/i.test(type)) {
      lands++;
    }
  }
  const selectTab = (t: "deck" | "neighbors") => {
    setTab(t);
    setOpen(true);
  };

  return (
    <div className="hidden shrink-0 flex-col lg:flex">
      <PanelBar open={open} canCollapse onToggle={() => setOpen((v) => !v)} onResizeStart={beginResize}>
        <BottomBar
          activeName={activeName}
          activeAvatarUrl={activeAvatarUrl}
          tab={activeTab}
          onTab={selectTab}
          total={cards.length}
          creatures={creatures}
          lands={lands}
          left={left}
          right={right}
          passRight={passRight}
        />
      </PanelBar>
      <div
        className="relative shrink-0 overflow-hidden bg-surface/60"
        style={{ height: open ? height : 0, transition: dragging ? "none" : "height 200ms ease" }}
      >
        {activeTab === "deck" ? (
          <div className="relative flex h-full py-1 pl-6">
            <div className={cn("absolute bottom-2 z-20", showSideboard ? "right-[200px]" : "right-6")}>
              <PoolControls
                canSplit={canSplit}
                splitSideboard={splitSideboard}
                onToggleSplit={onToggleSplit}
                onOpenDeck={onOpenDeck}
                deckLayout={deckLayout}
                onToggleDeckLayout={onToggleDeckLayout}
              />
            </div>
            <PoolCards
              order={order}
              rows={rows}
              cards={cards}
              lastInSideboard={lastInSideboard}
              splitSideboard={splitSideboard}
              sideboard={sideboard}
              cardWidth={DECK_CARD_WIDTH}
              reveal={order ? DECK_ORDER_REVEAL : DECK_CURVE_REVEAL}
              sideReveal={DECK_SIDE_REVEAL}
              groupByType
            />
          </div>
        ) : (
          <NeighborColumns left={leftPile} center={centerPile} right={rightPile} />
        )}
      </div>
    </div>
  );
}

const DECK_CARD_WIDTH = 176;
const DECK_CURVE_REVEAL = 28;
const DECK_ORDER_REVEAL = 44;
const DECK_SIDE_REVEAL = 24;
const CARD_ASPECT = 1.4;
const DECK_PANEL_MAX_FRACTION = 0.72;
const DECK_PANEL_FLOOR = 120;
const DECK_WRAPPER_PAD_Y = 4;
const REVIEW_HEADER_HEIGHT = 60;
const DECK_PANEL_BAR_HEIGHT = 40;

function useViewportHeight() {
  const [viewportHeight, setViewportHeight] = useState(() => (typeof window === "undefined" ? 900 : window.innerHeight));
  useEffect(() => {
    const onResize = () => setViewportHeight(window.innerHeight);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return viewportHeight;
}

function deckPanelDefaultHeight(viewportHeight: number, boosterHeight: number) {
  const oneCard = Math.ceil(DECK_CARD_WIDTH * CARD_ASPECT + POOL_PAD * 2 + DECK_WRAPPER_PAD_Y * 2);
  const cap = Math.min(oneCard, viewportHeight * DECK_PANEL_MAX_FRACTION);
  const leftoverBelowBooster = viewportHeight - REVIEW_HEADER_HEIGHT - DECK_PANEL_BAR_HEIGHT - boosterHeight;
  return Math.max(DECK_PANEL_FLOOR, Math.min(cap, leftoverBelowBooster));
}

function BottomBar({
  activeName,
  activeAvatarUrl,
  tab,
  onTab,
  total,
  creatures,
  lands,
  left,
  right,
  passRight,
}: {
  activeName: string;
  activeAvatarUrl: string | null;
  tab: "deck" | "neighbors";
  onTab: (t: "deck" | "neighbors") => void;
  total: number;
  creatures: number;
  lands: number;
  left: Seat;
  right: Seat;
  passRight: boolean;
}) {
  const arrow = passRight ? "»" : "«";
  return (
    <div className="relative flex h-full w-full items-center font-display">
      {tab === "deck" ? (
        <>
          <div className="flex w-1/2 min-w-0 items-center justify-center gap-2 text-[15px] tracking-[0.08em]">
            <AAvatar displayName={activeName} avatarUrl={activeAvatarUrl} size={22} green />
            <span className="max-w-[220px] truncate text-green">{activeName}</span>
          </div>
          <div className="absolute left-1/2 flex -translate-x-1/2 items-center gap-3.5 text-[14px] tracking-[0.08em]">
            <span className="tracking-[0.16em] text-subtle">DECK</span>
            <DeckBarStat n={total} label="CARDS" />
            <DeckBarStat n={creatures} label="CREATURES" />
            <DeckBarStat n={lands} label="LANDS" />
            <DeckBarStat n={total - creatures - lands} label="SPELLS" />
          </div>
        </>
      ) : (
        <div className="flex w-full items-stretch text-[14px] tracking-[0.08em]">
          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 pr-3">
            <NeighborName seat={left} />
            <span className="font-mono text-muted">{arrow}</span>
          </div>
          <div className="w-0.5 shrink-0" />
          <div className="flex min-w-0 flex-[1.7] items-center justify-center gap-2 text-[15px]">
            <AAvatar displayName={activeName} avatarUrl={activeAvatarUrl} size={20} green />
            <span className="max-w-[220px] truncate text-green">{activeName}</span>
          </div>
          <div className="w-0.5 shrink-0" />
          <div className="flex min-w-0 flex-1 items-center justify-start gap-2 pl-3">
            <span className="font-mono text-muted">{arrow}</span>
            <NeighborName seat={right} />
          </div>
        </div>
      )}
      <span className="absolute right-4 top-1/2 -translate-y-1/2" onPointerDown={(e) => e.stopPropagation()}>
        <ShowNeighborsToggle
          on={tab === "neighbors"}
          onToggle={() => onTab(tab === "neighbors" ? "deck" : "neighbors")}
        />
      </span>
    </div>
  );
}

function NeighborName({ seat }: { seat: Seat }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <AAvatar displayName={seat.name} avatarUrl={seat.avatarUrl} size={18} />
      <span className="max-w-[150px] truncate text-subtle">{seat.name}</span>
    </span>
  );
}

function NeighborColumns({ left, center, right }: { left: Pile; center: Pile; right: Pile }) {
  return (
    <div className="flex h-full items-stretch">
      <div className="min-w-0 flex-1 pt-2">
        <Pool cards={left.main} sideboard={left.board} lastPickInSideboard={left.lastInSide} markLast cardWidth={140} reveal={22} />
      </div>
      <div className="w-0.5 shrink-0 self-stretch bg-border" />
      <div className="min-w-0 flex-[1.7] pt-2">
        <Pool cards={center.main} sideboard={center.board} lastPickInSideboard={center.lastInSide} markLast cardWidth={166} reveal={26} />
      </div>
      <div className="w-0.5 shrink-0 self-stretch bg-border" />
      <div className="min-w-0 flex-1 pt-2">
        <Pool cards={right.main} sideboard={right.board} lastPickInSideboard={right.lastInSide} markLast cardWidth={140} reveal={22} align="right" />
      </div>
    </div>
  );
}

function PoolControls({
  canSplit,
  splitSideboard,
  onToggleSplit,
  onOpenDeck,
  deckLayout,
  onToggleDeckLayout,
}: {
  canSplit: boolean;
  splitSideboard: boolean;
  onToggleSplit: () => void;
  onOpenDeck?: () => void;
  deckLayout: "order" | "columns";
  onToggleDeckLayout: () => void;
}) {
  const pill = "flex h-7 items-center justify-center gap-1.5 rounded border px-2.5 font-display text-[11px] tracking-[0.12em] transition-colors lg:h-8 lg:rounded-md lg:px-3 lg:text-[13px]";
  const idle = "border-border bg-surface2 text-subtle hover:border-white/40 hover:text-text";
  const active = "border-green/60 bg-surface2 text-green [background-image:linear-gradient(rgba(46,232,92,0.15),rgba(46,232,92,0.15))]";
  return (
    <div className="flex flex-col items-stretch gap-1.5">
      {(onOpenDeck || canSplit) && (
        <div className="flex w-full gap-1.5">
          {onOpenDeck && (
            <button onClick={onOpenDeck} className={cn(pill, idle, "flex-1")}>
              DECK
              <TbCards size={14} aria-hidden="true" />
            </button>
          )}
          {canSplit && (
            <Tooltip label={splitSideboard ? "Merge the sideboard into the deck column" : "Split the sideboard into its own panel"} side="top">
              <button
                onClick={onToggleSplit}
                aria-pressed={splitSideboard}
                className={cn(pill, splitSideboard ? active : idle, "flex-1")}
              >
                SIDE
                <GoSidebarCollapse size={15} aria-hidden="true" />
              </button>
            </Tooltip>
          )}
        </div>
      )}
      <LayoutToggle layout={deckLayout} onToggle={onToggleDeckLayout} />
    </div>
  );
}

// The final sideboard cut as a single stacked column to the right of the deck. Cards fan top-to-bottom
// like a pool column; the last-pick glow lands here when the most recent pick was ultimately cut.
function SideboardPane({
  cards,
  markLast,
  cardWidth,
  reveal,
}: {
  cards: ArtifactCard[];
  markLast: boolean;
  cardWidth: number;
  reveal: number;
}) {
  return (
    <div className="flex shrink-0 flex-col">
      <div className="themed-scrollbar min-h-0 flex-1 overflow-y-auto overflow-x-hidden py-2 pl-0.5 pr-2">
        <StackColumn
          count={cards.length}
          reveal={reveal}
          width={cardWidth}
          cardClassName={POOL_CARD_CLASS}
          glowIndex={markLast ? cards.length - 1 : null}
          cardAt={(i) => cards[i]}
          renderCard={(i) => <CardImage card={cards[i]} />}
        />
      </div>
    </div>
  );
}

// Mobile-only: the pick navigator sits on top of the deck, doubling as its divider. Pack chips let
// you jump packs instead of stepping 14+ times; prev/next walk picks within the pack.
function MobileNavDivider({
  pack,
  pick,
  onJump,
  onPrev,
  onNext,
  atStart,
  atEnd,
  awaitingReveal,
  onReveal,
  revealMode,
  onRevealMode,
}: {
  pack: number;
  pick: number;
  onJump: (pack: number, pick: number) => void;
  onPrev: () => void;
  onNext: () => void;
  atStart: boolean;
  atEnd: boolean;
  awaitingReveal: boolean;
  onReveal: () => void;
  revealMode: RevealMode;
  onRevealMode: (m: RevealMode) => void;
}) {
  const arrow = "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border transition-[transform,background-color,border-color,color] duration-150 ease-out touch-manipulation [-webkit-tap-highlight-color:transparent]";
  return (
    <div className="flex h-12 shrink-0 items-center justify-between gap-1.5 border-t border-border bg-surface px-2 lg:hidden">
      <div className="flex gap-1">
        {[0, 1, 2].map((p) => (
          <button
            key={p}
            onClick={() => onJump(p, 0)}
            className={cn(
              "flex h-8 min-w-[30px] items-center justify-center rounded border px-1.5 font-display text-[15px] tracking-[0.04em] tabular-nums transition-colors",
              p === pack
                ? "border-green/60 bg-green/15 text-green"
                : "border-border bg-surface2 text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text",
            )}
          >
            {p + 1}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={onPrev}
          disabled={atStart}
          aria-label="Previous pick"
          className={cn(arrow, atStart ? "border-border text-dim opacity-40" : "border-white/40 bg-surface2 text-text active:scale-90 active:bg-white/20 motion-reduce:active:scale-100")}
        >
          <ChevronIcon dir="left" />
        </button>
        <span className="min-w-[56px] text-center font-display text-[17px] tracking-[0.06em] text-text">
          P{pack + 1}P{pick + 1}
        </span>
        <button
          onClick={awaitingReveal ? onReveal : onNext}
          disabled={!awaitingReveal && atEnd}
          aria-label={awaitingReveal ? "Reveal picked card" : "Next pick"}
          className={cn(arrow, !awaitingReveal && atEnd ? "border-border text-dim opacity-40" : "border-white/40 bg-surface2 text-text active:scale-90 active:bg-white/20 motion-reduce:active:scale-100")}
        >
          {awaitingReveal ? <EyeIcon off={false} /> : <ChevronIcon dir="right" />}
        </button>
      </div>

      <ShowPicksToggle
        showPicks={revealMode === "revealed"}
        onToggle={() => onRevealMode(revealMode === "revealed" ? "click" : "revealed")}
      />
    </div>
  );
}

function LayoutToggle({ layout, onToggle }: { layout: "order" | "columns"; onToggle: () => void }) {
  return (
    <div className="flex w-full rounded border border-border bg-surface2 p-0.5 font-display text-[10px] tracking-[0.1em] lg:rounded-md lg:p-1 lg:text-[13px] lg:tracking-[0.12em]">
      <button
        onClick={() => layout !== "columns" && onToggle()}
        className={cn("flex-1 rounded px-2 py-1 text-center lg:px-3.5 lg:py-1.5", layout === "columns" ? "bg-green/15 text-green" : "text-muted hover:text-subtle")}
      >
        CURVE
      </button>
      <button
        onClick={() => layout !== "order" && onToggle()}
        className={cn("flex-1 rounded px-2 py-1 text-center lg:px-3.5 lg:py-1.5", layout === "order" ? "bg-green/15 text-green" : "text-muted hover:text-subtle")}
      >
        ORDER
      </button>
    </div>
  );
}

// Order view: one row of columns by pick position; every pack piles at its position (P1P1 on top,
// then P2P1, then P3P1), the same fanned treatment the curve uses by cost. Single horizontal scroll.
function OrderStrip({
  rows,
  sideboard = [],
  lastPickInSideboard = false,
  markLast = false,
  cardWidth,
  reveal,
}: {
  rows: ArtifactCard[][];
  sideboard?: ArtifactCard[];
  lastPickInSideboard?: boolean;
  markLast?: boolean;
  cardWidth: number;
  reveal: number;
}) {
  const positions = rows.reduce((max, r) => Math.max(max, r.length), 0);
  let lastRow = -1;
  for (let r = 0; r < rows.length; r++) {
    if (rows[r].length > 0) {
      lastRow = r;
    }
  }
  const lastCol = lastRow >= 0 ? rows[lastRow].length - 1 : -1;
  const glowStrip = markLast && !lastPickInSideboard;
  return (
    <div className="themed-scrollbar flex h-full items-start gap-1 overflow-x-auto px-2 py-2">
      {Array.from({ length: positions }, (_, i) => {
        const stack = rows.map((r, ri) => ({ card: r[i], ri })).filter((e) => e.card);
        return (
          <div
            key={i}
            className="relative shrink-0"
            style={{ width: cardWidth, height: Math.max(0, stack.length - 1) * reveal + cardWidth * 1.4 }}
          >
            {stack.map(({ card, ri }, di) => (
              <div
                key={di}
                className={cn(
                  "absolute w-full overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)]",
                  glowStrip && ri === lastRow && i === lastCol && "review-last-pick z-10",
                )}
                style={{ top: di * reveal }}
              >
                <CardImage card={card} />
              </div>
            ))}
          </div>
        );
      })}
      {sideboard.length > 0 && <div className="shrink-0" style={{ width: Math.round(cardWidth * SIDE_COLUMN_GAP_RATIO) }} />}
      {sideboard.length > 0 && (
        <div
          className="relative shrink-0"
          style={{ width: cardWidth, height: Math.max(0, sideboard.length - 1) * reveal + cardWidth * 1.4 }}
        >
          {sideboard.map((card, di) => (
            <div
              key={di}
              className={cn(
                "absolute w-full overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)]",
                markLast && lastPickInSideboard && di === sideboard.length - 1 && "review-last-pick z-10",
              )}
              style={{ top: di * reveal }}
            >
              <CardImage card={card} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

type PoolEntry = { card: ArtifactCard; idx: number };

const POOL_PAD = 8;
const POOL_GAP = 4;
const SIDE_COLUMN_GAP_RATIO = 0.1;
const POOL_CARD_CLASS =
  "overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)] transition-[outline-color] group-hover:outline-white/50 hover:outline-white/50";

function Pool({
  cards,
  sideboard = [],
  lastPickInSideboard = false,
  groupByType = false,
  align = "left",
  cardWidth = 116,
  reveal = 26,
  markLast = false,
}: {
  cards: ArtifactCard[];
  sideboard?: ArtifactCard[];
  lastPickInSideboard?: boolean;
  groupByType?: boolean;
  align?: "left" | "right";
  cardWidth?: number;
  reveal?: number;
  markLast?: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [poolWidth, setPoolWidth] = useState(0);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!groupByType || !el) {
      return;
    }
    const measure = () => setPoolWidth(el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [groupByType]);
  const column = (key: string, group: PoolEntry[], lastIndex: number, glow: boolean) => (
    <StackColumn
      key={key}
      count={group.length}
      reveal={reveal}
      width={cardWidth}
      className="shrink-0"
      cardClassName={POOL_CARD_CLASS}
      glowIndex={glow ? group.findIndex((e) => e.idx === lastIndex) : null}
      cardAt={(i) => group[i].card}
      renderCard={(i) => <CardImage card={group[i].card} />}
    />
  );
  const entries = cards.map((card, idx) => ({ card, idx }));
  const lastIndex = cards.length - 1;
  const glow = markLast && !lastPickInSideboard;

  let track;
  if (groupByType) {
    const isCreature = (card: ArtifactCard) => /creature/i.test(card.type ?? "");
    const isLand = (card: ArtifactCard) => /land/i.test(card.type ?? "");
    const creatureCols = creatureCurveColumns(entries.filter((e) => isCreature(e.card)));
    const lands = entries.filter((e) => !isCreature(e.card) && isLand(e.card));
    let spellCols = cmcColumns(entries.filter((e) => !isCreature(e.card) && !isLand(e.card)));
    if (spellCols.length > 4) {
      spellCols = groupLowSpellColumns(spellCols);
    }
    const spacerWidth = Math.round(cardWidth * SIDE_COLUMN_GAP_RATIO);
    const landWidth = lands.length > 0 ? cardWidth : spacerWidth;
    const sideWidth = sideboard.length > 0 ? spacerWidth + cardWidth : 0;
    const available = poolWidth > 0 ? poolWidth - POOL_PAD * 2 : Infinity;
    const trackWidth = () => {
      const elementCount = creatureCols.length + 1 + spellCols.length + (sideboard.length > 0 ? 2 : 0);
      const columnsWidth = (creatureCols.length + spellCols.length) * cardWidth + landWidth + sideWidth;
      return columnsWidth + Math.max(0, elementCount - 1) * POOL_GAP;
    };
    while (spellCols.length > 1 && trackWidth() > available) {
      const last = spellCols[spellCols.length - 1];
      const prev = spellCols[spellCols.length - 2];
      spellCols = [...spellCols.slice(0, -2), [prev[0], [...prev[1], ...last[1]]]];
    }
    track = (
      <>
        {creatureCols.map((group, i) => column(`c${i}`, group, lastIndex, glow))}
        {lands.length > 0 ? (
          column("lands", lands, lastIndex, glow)
        ) : (
          <div key="land-gap" className="shrink-0" style={{ width: spacerWidth }} />
        )}
        {spellCols.map(([, group], i) => column(`o${i}`, group, lastIndex, glow))}
        {sideboard.length > 0 && <div key="side-gap" className="shrink-0" style={{ width: spacerWidth }} />}
        {sideboard.length > 0 &&
          column(
            "side",
            sideboard.map((card, idx) => ({ card, idx })),
            sideboard.length - 1,
            markLast && lastPickInSideboard,
          )}
      </>
    );
  } else {
    track = (
      <>
        {cmcColumns(entries).map(([cmc, group]) => column(`m${cmc}`, group, lastIndex, glow))}
        {sideboard.length > 0 &&
          column(
            "side",
            sideboard.map((card, idx) => ({ card, idx })),
            sideboard.length - 1,
            markLast && lastPickInSideboard,
          )}
      </>
    );
  }
  return (
    <div ref={scrollRef} className="themed-scrollbar h-full overflow-auto" style={{ padding: POOL_PAD }}>
      <div className={cn("flex w-max items-start", align === "right" && "ml-auto")} style={{ gap: POOL_GAP }}>
        {track}
      </div>
    </div>
  );
}

function creatureCurveColumns(entries: PoolEntry[]): PoolEntry[][] {
  if (entries.length === 0) {
    return [];
  }
  const byCmc = new Map<number, PoolEntry[]>();
  let minCmc = 2;
  let maxCmc = 2;
  for (const entry of entries) {
    const cmc = Math.max(0, Math.round(entry.card.cmc ?? 0));
    minCmc = Math.min(minCmc, cmc);
    maxCmc = Math.max(maxCmc, cmc);
    const list = byCmc.get(cmc);
    if (list) {
      list.push(entry);
    } else {
      byCmc.set(cmc, [entry]);
    }
  }
  const columns: PoolEntry[][] = [];
  for (let cmc = minCmc; cmc <= maxCmc; cmc++) {
    columns.push(byCmc.get(cmc) ?? []);
  }
  return columns;
}

function groupLowSpellColumns(columns: [number, PoolEntry[]][]): [number, PoolEntry[]][] {
  const cheap: PoolEntry[] = [];
  const rest: [number, PoolEntry[]][] = [];
  for (const [cmc, group] of columns) {
    if (cmc === 1 || cmc === 2) {
      cheap.push(...group);
    } else {
      rest.push([cmc, group]);
    }
  }
  if (cheap.length === 0) {
    return columns;
  }
  return [[2, cheap], ...rest];
}

function cmcColumns(entries: PoolEntry[]): [number, PoolEntry[]][] {
  const byCmc = new Map<number, PoolEntry[]>();
  let maxCmc = 0;
  for (const entry of entries) {
    const cmc = Math.max(0, Math.round(entry.card.cmc ?? 0));
    maxCmc = Math.max(maxCmc, cmc);
    const list = byCmc.get(cmc);
    if (list) {
      list.push(entry);
    } else {
      byCmc.set(cmc, [entry]);
    }
  }
  const columns: [number, PoolEntry[]][] = [];
  for (let c = 1; c <= maxCmc; c++) {
    const group = byCmc.get(c) ?? [];
    if (group.length === 0) {
      continue;
    }
    columns.push([c, group]);
  }
  const lands = byCmc.get(0) ?? [];
  if (lands.length) {
    columns.push([0, lands]);
  }
  return columns;
}

function PassArrow({ dir }: { dir: "up" | "down" | "left" | "right" }) {
  const rotation = { right: "", left: "rotate-180", down: "rotate-90", up: "-rotate-90" }[dir];
  return <span className={cn("inline-block font-mono text-[15px] leading-none text-subtle", rotation)}>»</span>;
}

// Two columns of four seats laid out so the arrows trace the pack-pass loop around the table: across the
// top, down one column, across the bottom, up the other. The loop reverses for the right-to-left packs.
const RING: { left: number; right: number; top?: boolean; bottom?: boolean }[] = [
  { left: 0, right: 1, top: true },
  { left: 7, right: 2 },
  { left: 6, right: 3 },
  { left: 5, right: 4, bottom: true },
];

function PlayerGrid({
  seats,
  activeSeat,
  onSelect,
  passRight,
}: {
  seats: Seat[];
  activeSeat: number;
  onSelect: (i: number) => void;
  passRight: boolean;
}) {
  const topDir = passRight ? "right" : "left";
  const bottomDir = passRight ? "left" : "right";
  const leftColDir = passRight ? "up" : "down";
  const rightColDir = passRight ? "down" : "up";
  const arrowRiseToAvatar = 20;
  const tile = (i: number) => (
    <PlayerTile seat={seats[i]} active={i === activeSeat} onClick={() => onSelect(i)} />
  );
  return (
    <div className="flex h-full flex-col px-1.5 py-2">
      {RING.map((row, i) => (
        <div key={i} className="relative flex flex-1 items-stretch">
          {tile(row.left)}
          {tile(row.right)}
          {(row.top || row.bottom) && (
            <span
              className="pointer-events-none absolute left-1/2 top-1/2"
              style={{ transform: `translate(-50%, calc(-50% - ${arrowRiseToAvatar}px))` }}
            >
              <PassArrow dir={row.top ? topDir : bottomDir} />
            </span>
          )}
          {i < RING.length - 1 && (
            <>
              <span className="pointer-events-none absolute bottom-0 left-1/4 -translate-x-1/2 translate-y-1/2">
                <PassArrow dir={leftColDir} />
              </span>
              <span className="pointer-events-none absolute bottom-0 left-3/4 -translate-x-1/2 translate-y-1/2">
                <PassArrow dir={rightColDir} />
              </span>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

function PlayerTile({
  seat,
  active,
  onClick,
}: {
  seat: Seat;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex h-full w-full min-w-0 flex-col items-center justify-center gap-1.5 rounded-lg px-2 transition-colors",
        active ? "bg-white/[0.06]" : "hover:bg-white/[0.04]",
      )}
    >
      <AAvatar displayName={seat.name} avatarUrl={seat.avatarUrl} size={58} green={active} />
      <span
        className={cn(
          "max-w-full truncate font-display text-[15px] leading-none tracking-[0.04em]",
          active ? "text-green" : "text-subtle",
        )}
      >
        {seat.name}
      </span>
      <Pips colors={seat.colors} size={14} flat />
    </button>
  );
}

function NavArrow({ dir, onClick, disabled }: { dir: "prev" | "next"; onClick?: () => void; disabled?: boolean }) {
  const primary = dir === "next";
  const label = primary ? "Next Pick" : "Previous Pick";
  const tooltip = primary ? "Next Pick (Arrow Right)" : "Previous Pick (Arrow Left)";
  const [hover, setHover] = useState(false);
  return (
    <Tooltip label={tooltip} side="bottom" open={hover && !disabled}>
      <button
        onClick={onClick}
        onPointerEnter={(e) => e.pointerType === "mouse" && setHover(true)}
        onPointerLeave={() => setHover(false)}
        disabled={disabled}
        aria-label={label}
        className={cn(
          "flex h-9 items-center justify-center rounded-md border bg-surface2",
          primary ? "min-w-[84px] gap-1.5 px-3 font-display text-[13px] tracking-[0.12em]" : "w-9",
          "transition-[transform,background-color,border-color,color] duration-150 ease-out",
          "touch-manipulation [-webkit-tap-highlight-color:transparent]",
          disabled
            ? "border-border text-dim opacity-40"
            : "border-white/40 text-text hover:border-white/60 hover:bg-white/10 active:scale-90 active:bg-white/20 motion-reduce:active:scale-100",
        )}
      >
        {primary && <span>NEXT</span>}
        <ChevronIcon dir={primary ? "right" : "left"} />
      </button>
    </Tooltip>
  );
}

function ChevronIcon({ dir }: { dir: "up" | "down" | "left" | "right" }) {
  const path = {
    up: "M6 15l6-6 6 6",
    down: "M6 9l6 6 6-6",
    left: "M15 18l-6-6 6-6",
    right: "M9 6l6 6-6 6",
  }[dir];
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
      {off && <line x1="3" y1="3" x2="21" y2="21" />}
    </svg>
  );
}
