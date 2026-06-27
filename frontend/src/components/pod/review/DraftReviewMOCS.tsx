import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";

import { cn } from "../../../lib/utils";
import { Pips } from "../../ManaPips";
import { Tooltip } from "../../Tooltip";
import { GoSidebarCollapse, TbCards } from "../../Icons";
import { avatarAccent, CardImage } from "./ReviewCard";
import { DeckScreenshotModal, type DeckLike } from "../DeckScreenshotModal";
import { poolBefore, poolByPack, reconstructDraft, resolveDeck, seatColors, seatHandle } from "../../../data/draft-artifact";
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
  deckColors: string | null;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption: string | null;
  record: string | null;
  draftLogUrl: string | null;
}

interface DraftReviewMOCSProps {
  artifact: PodDraftArtifact;
  meta: DraftReviewMeta;
  initialSeat?: number;
  onClose?: () => void;
  onSeatChange?: (seatIndex: number) => void;
  eventId?: string;
  seatInfo?: ReviewSeatInfo[];
}

export function DraftReviewMOCS({ artifact, meta, initialSeat = 0, onClose, onSeatChange, eventId, seatInfo }: DraftReviewMOCSProps) {
  const setSymbol = `/set-symbols/${meta.setCode.toLowerCase()}.png`;
  const eventTitle = useMemo(
    () =>
      meta.name
        .replace(new RegExp(`^${meta.setCode}\\s+`, "i"), "")
        .replace(/\s*[-–]\s*[^-–]*$/, "")
        .trim(),
    [meta],
  );
  const N = artifact.seats.length;

  const views = useMemo(() => reconstructDraft(artifact), [artifact]);
  const seats = useMemo(
    () => artifact.seats.map((name, i) => ({ index: i, name: seatHandle(name), colors: seatColors(artifact, i) })),
    [artifact],
  );

  const [seat, setSeat] = useState(initialSeat);
  const [pack, setPack] = useState(0);
  const [pick, setPick] = useState(0);
  const [showNeighbors, setShowNeighbors] = useState(true);
  const [showTable, setShowTable] = useState(true);
  const [hideColors, setHideColors] = useState(false);
  const [deckLayout, setDeckLayout] = usePersistentState<"order" | "columns">("draftReviewDeckLayout", "columns");
  const [revealMode, setRevealMode] = usePersistentState<RevealMode>("draftReviewRevealMode", "click");
  const [revealed, setRevealed] = useState(false);
  const [splitSideboard, setSplitSideboard] = useState(false);
  const [deckPopupSeat, setDeckPopupSeat] = useState<number | null>(null);

  const seatInfoMap = useMemo(() => new Map((seatInfo ?? []).map((s) => [s.seatIndex, s])), [seatInfo]);

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
    if (pick + 1 < packSize) {
      goTo(pack, pick + 1);
    } else if (pack < 2) {
      goTo(pack + 1, 0);
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
    onSeatChange?.(i);
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

  const view = views[seat][pack][pick];
  const boosterCards = view.booster.map((idx) => artifact.cards[idx]);
  const active = seats[seat];

  const deck = artifact.decks?.[seat];
  const sideSet = useMemo(() => new Set(deck?.side ?? []), [deck]);
  const canSplit = (deck?.side?.length ?? 0) > 0;
  const splitActive = splitSideboard && canSplit;

  const toCards = (indices: number[]) => indices.map((idx) => artifact.cards[idx]);
  const poolIdx = poolBefore(views, seat, pack, pick);
  const poolRowsIdx = poolByPack(views, seat, pack, pick);
  const pool = toCards(splitActive ? poolIdx.filter((idx) => !sideSet.has(idx)) : poolIdx);
  const poolRows = (splitActive ? poolRowsIdx.map((row) => row.filter((idx) => !sideSet.has(idx))) : poolRowsIdx).map(toCards);
  const sideboardCards = splitActive ? toCards(poolIdx.filter((idx) => sideSet.has(idx))) : [];
  const lastPickIdx = poolIdx.length > 0 ? poolIdx[poolIdx.length - 1] : null;
  const lastInSideboard = splitActive && lastPickIdx != null && sideSet.has(lastPickIdx);

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
      draftLogUrl: info.draftLogUrl,
    };
  }

  const left = (seat - 1 + N) % N;
  const right = (seat + 1) % N;
  const dir = PASS_DIRS[pack];
  const fromSeat = dir === 1 ? left : right;
  const toSeat = dir === 1 ? right : left;

  const leftCards = poolBefore(views, left, pack, pick).map((i) => artifact.cards[i]);
  const rightCards = poolBefore(views, right, pack, pick).map((i) => artifact.cards[i]);
  const neighborsHaveCards = leftCards.length > 0 || rightCards.length > 0;
  const neighborsOpen = showNeighbors && neighborsHaveCards;

  return (
    <div className="fixed inset-0 z-50 flex select-none flex-col bg-bg text-text">
      <MobileTopBar
        setSymbol={setSymbol}
        eventTitle={eventTitle}
        from={seats[fromSeat]}
        active={active}
        to={seats[toSeat]}
        onSelectFrom={() => changeSeat(fromSeat)}
        onSelectTo={() => changeSeat(toSeat)}
        onClose={onClose}
      />
      <Header
        setSymbol={setSymbol}
        eventTitle={eventTitle}
        onClose={onClose}
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
        hideColors={hideColors}
        onToggleColors={() => setHideColors((v) => !v)}
      />
      <div className="relative flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          <BoosterPanel cards={boosterCards} pickedPos={pickShown ? view.takenPos : null} />
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
            expanded={!neighborsOpen}
            deckLayout={deckLayout}
            onToggleDeckLayout={() => setDeckLayout((l) => (l === "order" ? "columns" : "order"))}
            canSplit={canSplit}
            splitSideboard={splitSideboard}
            onToggleSplit={() => setSplitSideboard((v) => !v)}
            onOpenDeck={canOpenDeck ? () => setDeckPopupSeat(seat) : undefined}
          />
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
              hideColors={hideColors}
              passRight={dir === 1}
            />
          </div>
        </aside>
      </div>
      <PlayersBar
        show={showNeighbors}
        onToggle={() => setShowNeighbors((v) => !v)}
        canFold={neighborsHaveCards}
        left={seats[left]}
        active={active}
        right={seats[right]}
        passRight={dir === 1}
      />
      {neighborsOpen && <NeighborBand left={leftCards} right={rightCards} />}
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
  );
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

interface Seat {
  index: number;
  name: string;
  colors: string;
}

// Mobile-only slim bar: the pass flow from › active › to, names tight together. Tapping the upstream
// or downstream player switches seats, so you can walk the table. The › points the way cards pass.
function MobileTopBar({
  setSymbol,
  eventTitle,
  from,
  active,
  to,
  onSelectFrom,
  onSelectTo,
  onClose,
}: {
  setSymbol: string;
  eventTitle: string;
  from: Seat;
  active: Seat;
  to: Seat;
  onSelectFrom: () => void;
  onSelectTo: () => void;
  onClose?: () => void;
}) {
  return (
    <div className="relative flex h-10 shrink-0 items-center border-b border-border bg-surface px-2 lg:hidden">
      <button
        onClick={onClose}
        aria-label="Back to pod"
        className="absolute left-2 flex items-center gap-1.5 [-webkit-tap-highlight-color:transparent] active:text-text"
      >
        <img src={setSymbol} alt="" className="h-5 w-5" />
        <span className="max-w-[84px] truncate font-display text-[13px] tracking-[0.04em] text-subtle">{eventTitle}</span>
      </button>
      <div className="grid w-full grid-cols-[1fr_auto_1fr] items-center">
        <div className="flex min-w-0 items-center justify-end gap-2">
          <button
            onClick={onSelectFrom}
            className="max-w-[110px] truncate font-display text-[13px] tracking-[0.04em] text-subtle [-webkit-tap-highlight-color:transparent] active:text-text"
          >
            {from.name}
          </button>
          <span className="font-mono text-[13px] text-subtle">»</span>
        </div>
        <span className="max-w-[120px] truncate px-1 text-center font-display text-[16px] tracking-[0.06em] text-green">
          {active.name}
        </span>
        <div className="flex min-w-0 items-center justify-start gap-2">
          <span className="font-mono text-[13px] text-subtle">»</span>
          <button
            onClick={onSelectTo}
            className="max-w-[110px] truncate font-display text-[13px] tracking-[0.04em] text-subtle [-webkit-tap-highlight-color:transparent] active:text-text"
          >
            {to.name}
          </button>
        </div>
      </div>
      <button
        onClick={onClose}
        aria-label="Close"
        className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-md text-muted [-webkit-tap-highlight-color:transparent] active:bg-white/10"
      >
        ✕
      </button>
    </div>
  );
}

function Header({
  setSymbol,
  eventTitle,
  onClose,
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
  hideColors,
  onToggleColors,
}: {
  setSymbol: string;
  eventTitle: string;
  onClose?: () => void;
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
  hideColors: boolean;
  onToggleColors: () => void;
}) {
  const revealControl = awaitingReveal ? (
    <Tooltip label="Reveal picked card" side="bottom">
      <button
        onClick={onReveal}
        aria-label="Reveal picked card"
        className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface2 text-subtle transition-colors hover:border-white/40 hover:bg-white/10 hover:text-text"
      >
        <EyeIcon off={false} />
      </button>
    </Tooltip>
  ) : (
    <NavArrow dir="next" onClick={onNext} disabled={atEnd} />
  );

  return (
    <header className="hidden h-[60px] shrink-0 items-center gap-5 border-b border-border bg-surface px-5 lg:flex">
      <button
        onClick={onClose}
        className="flex min-w-0 flex-1 items-center gap-2.5 text-left transition-colors hover:text-green"
        aria-label="Back to pod"
      >
        <img src={setSymbol} alt="" className="h-7 w-7 shrink-0" />
        <span className="truncate font-display text-[19px] tracking-[0.08em]">{eventTitle}</span>
      </button>

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
        <ShowPicksToggle showPicks={revealMode === "revealed"} onToggle={() => onRevealMode(revealMode === "revealed" ? "click" : "revealed")} />
      </div>

      <div className="flex flex-1 items-center justify-end gap-2">
        {showTable && (
          <SwitchToggle
            label="COLORS"
            on={!hideColors}
            onToggle={onToggleColors}
            ariaLabel="Show colors"
            tooltip={hideColors ? "Show colors" : "Hide colors"}
          />
        )}
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
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
  tooltip: string;
  ariaLabel: string;
}) {
  return (
    <Tooltip label={tooltip} side="bottom">
      <button
        onClick={onToggle}
        role="switch"
        aria-checked={on}
        aria-label={ariaLabel}
        className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-border bg-surface2 px-2.5 transition-colors [-webkit-tap-highlight-color:transparent] hover:border-white/40 hover:bg-white/10"
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

function ShowPicksToggle({ showPicks, onToggle }: { showPicks: boolean; onToggle: () => void }) {
  return (
    <SwitchToggle
      label="SHOW PICKS"
      on={showPicks}
      onToggle={onToggle}
      ariaLabel="Show picks"
      tooltip={showPicks ? "On: picks show as you navigate" : "Off: each pick stays hidden until you reveal it"}
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

function BoosterPanel({ cards, pickedPos }: { cards: ArtifactCard[]; pickedPos: number | null }) {
  return (
    <div className="themed-scrollbar min-h-0 flex-1 overflow-y-auto px-2 pb-2 pt-1.5 lg:px-6 lg:py-4">
      <div className="flex flex-wrap justify-center gap-1.5 lg:gap-2">
        {cards.map((card, i) => (
          <div key={i} className="w-[calc((100%-1.125rem)/4)] sm:w-[calc((100%-1.5rem)/5)] lg:w-[200px]">
            <BoosterCard card={card} picked={i === pickedPos} />
          </div>
        ))}
      </div>
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

const POOL_HEIGHT_KEY = "draftReviewPoolHeight";

function PoolBar({
  cards,
  rows,
  sideboard,
  lastInSideboard,
  expanded,
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
  expanded: boolean;
  deckLayout: "order" | "columns";
  onToggleDeckLayout: () => void;
  canSplit: boolean;
  splitSideboard: boolean;
  onToggleSplit: () => void;
  onOpenDeck?: () => void;
}) {
  const order = deckLayout === "order";
  const baseHeight = order ? 368 : expanded ? 452 : 300;
  const [dragHeight, setDragHeight] = useState<number | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    const stored = window.localStorage.getItem(POOL_HEIGHT_KEY);
    return stored ? Number(stored) : null;
  });
  const height = dragHeight ?? baseHeight;

  useEffect(() => {
    if (dragHeight != null) {
      window.localStorage.setItem(POOL_HEIGHT_KEY, String(dragHeight));
    }
  }, [dragHeight]);

  const beginResize = (startY: number) => {
    const startHeight = height;
    const onMove = (ev: PointerEvent) => {
      const next = startHeight - (ev.clientY - startY);
      setDragHeight(Math.min(window.innerHeight * 0.72, Math.max(150, next)));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const showSideboard = splitSideboard && sideboard.length > 0;
  const cardWidth = expanded ? 176 : 167;
  const controls = (
    <PoolControls
      canSplit={canSplit}
      splitSideboard={splitSideboard}
      onToggleSplit={onToggleSplit}
      onOpenDeck={onOpenDeck}
      deckLayout={deckLayout}
      onToggleDeckLayout={onToggleDeckLayout}
    />
  );

  return (
    <>
      <div className="relative shrink-0 border-t border-border bg-surface/60 px-2 py-2 lg:hidden">
        <div className="absolute bottom-2 right-2 z-10">{controls}</div>
        <div className={cn("flex gap-2", order ? "h-[24dvh]" : "h-[32dvh]")}>
          <div className="min-w-0 flex-1">
            {order ? (
              <OrderStrip rows={rows} markLast={!lastInSideboard} cardWidth={94} reveal={26} />
            ) : (
              <Pool cards={cards} markLast={!lastInSideboard} cardWidth={94} reveal={20} />
            )}
          </div>
          {showSideboard && <SideboardPane cards={sideboard} markLast={lastInSideboard} cardWidth={94} reveal={16} />}
        </div>
      </div>
      <div className="relative hidden shrink-0 border-t border-border bg-surface/60 lg:block" style={{ height }}>
        <div
          onPointerDown={(e) => {
            e.preventDefault();
            beginResize(e.clientY);
          }}
          className="group absolute inset-x-0 top-0 z-20 flex h-8 -translate-y-1/2 cursor-row-resize items-center justify-center"
          aria-label="Resize deck pool"
        >
          <span className="h-1.5 w-12 rounded-full bg-border2 transition-all group-hover:w-16 group-hover:bg-subtle" />
        </div>
        <div className="flex h-full py-3 pl-6">
          <div className="relative min-w-0 flex-1">
            <div className="absolute bottom-2 right-6 z-10">{controls}</div>
            {order ? (
              <OrderStrip rows={rows} markLast={!lastInSideboard} cardWidth={cardWidth} reveal={expanded ? 44 : 38} />
            ) : (
              <Pool cards={cards} markLast={!lastInSideboard} cardWidth={cardWidth} reveal={expanded ? 34 : 30} />
            )}
          </div>
          {showSideboard && <SideboardPane cards={sideboard} markLast={lastInSideboard} cardWidth={cardWidth} reveal={28} />}
        </div>
      </div>
    </>
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
            <button
              onClick={onToggleSplit}
              aria-pressed={splitSideboard}
              className={cn(pill, splitSideboard ? active : idle, "flex-1")}
            >
              SIDE
              <GoSidebarCollapse size={15} aria-hidden="true" />
            </button>
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
  const lastIndex = cards.length - 1;
  const cardClass =
    "w-full overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)]";
  return (
    <div className="flex shrink-0 flex-col" style={{ width: cardWidth }}>
      <div className="themed-scrollbar min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-2 py-2">
        <div className="relative w-full [display:flow-root]">
          {cards.slice(0, lastIndex).map((card, i) => (
            <div key={i} className={cn("absolute", cardClass)} style={{ top: i * reveal }}>
              <CardImage card={card} />
            </div>
          ))}
          <div
            className={cn("relative", cardClass, markLast && "review-last-pick z-10")}
            style={{ marginTop: lastIndex * reveal }}
          >
            <CardImage card={cards[lastIndex]} />
          </div>
        </div>
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
  const arrow = "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border font-mono text-[15px] transition-colors";
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
          className={cn(arrow, atStart ? "border-border text-dim opacity-40" : "border-border bg-surface2 text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text")}
        >
          ‹
        </button>
        <span className="min-w-[56px] text-center font-display text-[17px] tracking-[0.06em] text-text">
          P{pack + 1}P{pick + 1}
        </span>
        {awaitingReveal ? (
          <Tooltip label="Reveal picked card" side="bottom">
            <button onClick={onReveal} aria-label="Reveal picked card" className={cn(arrow, "border-border bg-surface2 text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text")}>
              <EyeIcon off={false} />
            </button>
          </Tooltip>
        ) : (
          <button
            onClick={onNext}
            disabled={atEnd}
            className={cn(arrow, atEnd ? "border-border text-dim opacity-40" : "border-border bg-surface2 text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text")}
          >
            ›
          </button>
        )}
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
  markLast = false,
  cardWidth,
  reveal,
}: {
  rows: ArtifactCard[][];
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
                  markLast && ri === lastRow && i === lastCol && "review-last-pick z-10",
                )}
                style={{ top: di * reveal }}
              >
                <CardImage card={card} />
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function Pool({
  cards,
  align = "left",
  cardWidth = 116,
  reveal = 26,
  markLast = false,
}: {
  cards: ArtifactCard[];
  align?: "left" | "right";
  cardWidth?: number;
  reveal?: number;
  markLast?: boolean;
}) {
  const lastIndex = cards.length - 1;
  const byCmc = new Map<number, { card: ArtifactCard; idx: number }[]>();
  let maxCmc = 0;
  for (let idx = 0; idx < cards.length; idx++) {
    const card = cards[idx];
    const cmc = Math.max(0, Math.round(card.cmc ?? 0));
    maxCmc = Math.max(maxCmc, cmc);
    const list = byCmc.get(cmc);
    if (list) {
      list.push({ card, idx });
    } else {
      byCmc.set(cmc, [{ card, idx }]);
    }
  }
  const columns: [number, { card: ArtifactCard; idx: number }[]][] = [];
  for (let c = 1; c <= maxCmc; c++) {
    const group = byCmc.get(c) ?? [];
    if (c === 1 && group.length === 0) {
      continue;
    }
    columns.push([c, group]);
  }
  const lands = byCmc.get(0) ?? [];
  if (lands.length) {
    columns.push([0, lands]);
  }
  return (
    <div
      className={cn(
        "themed-scrollbar flex h-full items-start gap-1 overflow-auto px-2 py-2",
        align === "right" ? "justify-end" : "justify-start",
      )}
    >
      {columns.map(([cmc, group]) => (
        <div
          key={cmc}
          className="relative shrink-0"
          style={{ width: cardWidth, height: Math.max(0, group.length - 1) * reveal + cardWidth * 1.4 }}
        >
          {group.map(({ card, idx }, i) => (
            <div
              key={i}
              className={cn(
                "absolute w-full overflow-hidden rounded-[5px] [outline-style:solid] outline-1 -outline-offset-1 outline-white/10 shadow-[0_-2px_6px_rgba(0,0,0,0.6)]",
                markLast && idx === lastIndex && "review-last-pick z-10",
              )}
              style={{ top: i * reveal }}
            >
              <CardImage card={card} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
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
  hideColors,
  passRight,
}: {
  seats: Seat[];
  activeSeat: number;
  onSelect: (i: number) => void;
  hideColors: boolean;
  passRight: boolean;
}) {
  const topDir = passRight ? "right" : "left";
  const bottomDir = passRight ? "left" : "right";
  const leftColDir = passRight ? "up" : "down";
  const rightColDir = passRight ? "down" : "up";
  const tile = (i: number) => (
    <PlayerTile seat={seats[i]} active={i === activeSeat} onClick={() => onSelect(i)} hideColors={hideColors} />
  );
  return (
    <div className="flex h-full flex-col px-1.5 py-2">
      {RING.map((row, i) => (
        <div key={i} className="relative flex flex-1 items-stretch">
          {tile(row.left)}
          {tile(row.right)}
          {(row.top || row.bottom) && (
            <span className="pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
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
  hideColors,
}: {
  seat: Seat;
  active: boolean;
  onClick: () => void;
  hideColors: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex h-full w-full flex-col items-center justify-center gap-1.5 rounded-lg px-2 transition-colors",
        active ? "bg-white/[0.06]" : "hover:bg-white/[0.04]",
      )}
    >
      <Avatar name={seat.name} colors={hideColors ? "" : seat.colors} size={58} />
      <span
        className={cn(
          "max-w-full truncate font-display text-[15px] leading-none tracking-[0.04em]",
          active ? "text-green" : "text-subtle",
        )}
      >
        {seat.name}
      </span>
      {!hideColors && <Pips colors={seat.colors} size={14} flat />}
    </button>
  );
}

function NeighborBand({ left, right }: { left: ArtifactCard[]; right: ArtifactCard[] }) {
  return (
    <div className="hidden h-[232px] shrink-0 items-stretch border-t border-border bg-bg lg:flex">
      <div className="min-w-0 flex-1 px-6 py-3">
        <Pool cards={left} markLast cardWidth={134} reveal={30} />
      </div>
      <div className="w-px shrink-0 self-stretch bg-border" />
      <div className="min-w-0 flex-1 px-6 py-3">
        <Pool cards={right} markLast cardWidth={134} reveal={30} align="right" />
      </div>
    </div>
  );
}

// Names the pass flow (from › active › to). Clicking anywhere folds the neighbor decks below; the chevron
// tab seated on this bar's top edge signals the action.
function PlayersBar({
  show,
  onToggle,
  canFold,
  left,
  active,
  right,
  passRight,
}: {
  show: boolean;
  onToggle: () => void;
  canFold: boolean;
  left: Seat;
  active: Seat;
  right: Seat;
  passRight: boolean;
}) {
  const arrow = passRight ? "»" : "«";
  const names = (
    <span className="mx-auto flex w-3/5 items-center">
      <span className="flex-1 truncate text-center font-display text-[15px] tracking-[0.08em] text-subtle">
        {left.name}
      </span>
      <span className="flex-1 text-center font-mono text-[14px] text-subtle">{arrow}</span>
      <span className="flex-1 truncate text-center font-display text-[15px] tracking-[0.08em] text-green">
        {active.name}
      </span>
      <span className="flex-1 text-center font-mono text-[14px] text-subtle">{arrow}</span>
      <span className="flex-1 truncate text-center font-display text-[15px] tracking-[0.08em] text-subtle">
        {right.name}
      </span>
    </span>
  );

  if (!canFold) {
    return (
      <div className="relative hidden h-9 w-full shrink-0 items-center justify-center border-t border-border bg-bg lg:flex">
        {names}
      </div>
    );
  }

  return (
    <Tooltip label={show ? "Hide neighbor picks" : "Show neighbor picks"} side="top">
      <button
        onClick={onToggle}
        aria-label={show ? "Hide neighbor picks" : "Show neighbor picks"}
        className="group relative hidden h-9 w-full shrink-0 items-center justify-center border-t border-border bg-bg transition-colors hover:bg-surface2 lg:flex"
      >
        <span className="absolute bottom-full left-1/2 flex -translate-x-1/2 translate-y-px items-center justify-center rounded-t-md border border-b-0 border-border bg-bg px-3 text-subtle transition-colors group-hover:bg-surface2 group-hover:text-text">
          <ChevronIcon dir={show ? "down" : "up"} />
        </span>
        {names}
      </button>
    </Tooltip>
  );
}

function Avatar({ name, colors, size }: { name: string; colors: string; size: number }) {
  const accent = avatarAccent(colors);
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-md border-2 bg-surface2"
      style={{ width: size, height: size, borderColor: accent }}
    >
      <span className="font-display tracking-[0.04em]" style={{ fontSize: size * 0.42, color: accent }}>
        {name.slice(0, 2).toUpperCase()}
      </span>
    </div>
  );
}

function NavArrow({ dir, onClick, disabled }: { dir: "prev" | "next"; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface2 font-mono text-[16px] transition-colors",
        disabled ? "text-dim opacity-40" : "text-subtle hover:border-white/40 hover:bg-white/10 hover:text-text",
      )}
    >
      {dir === "prev" ? "‹" : "›"}
    </button>
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
