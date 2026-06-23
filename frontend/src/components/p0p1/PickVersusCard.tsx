import { useEffect, useState, type MouseEvent } from "react";
import { createPortal } from "react-dom";
import { SlotPip } from "./slotVisuals";
import { pickPctLabel } from "../../data/p0p1Stats";
import type { PickVersus, PickVersusSide } from "../../types/p0p1";

const MAT = "#161b26";
const MUTED = "#7a8395";
const ROGUE = "#a98eff";
const GREEN = "#2ee85c";
const NEUTRAL = "#e6ecf5";

export function usePickVersusPager(list: PickVersus[]) {
  const [index, setIndex] = useState<number | null>(null);
  const current = index === null ? null : list[index] ?? null;
  return {
    list,
    index,
    current,
    open: (i: number) => setIndex(i),
    close: () => setIndex(null),
    step: (delta: number) =>
      setIndex((cur) => (cur === null ? cur : (cur + delta + list.length) % list.length)),
  };
}

export function PickVersusModal({ pager }: { pager: ReturnType<typeof usePickVersusPager> }) {
  const { current, index, list, close, step } = pager;

  useEffect(() => {
    if (current === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") step(-1);
      else if (e.key === "ArrowRight") step(1);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [current, close, step]);

  if (current === null || index === null) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-6"
      onClick={close}
    >
      <PickVersusCard
        versus={current}
        paged={list.length > 1}
        onPrev={() => step(-1)}
        onNext={() => step(1)}
      />
    </div>,
    document.body,
  );
}

export function PickVersusCard({
  versus,
  onPrev,
  onNext,
  paged = false,
}: {
  versus: PickVersus;
  onPrev?: () => void;
  onNext?: () => void;
  paged?: boolean;
}) {
  const stop = (e: MouseEvent) => e.stopPropagation();

  if (versus.agreed) {
    return (
      <div
        onClick={stop}
        className="flex max-h-[92vh] w-full max-w-[420px] flex-col overflow-hidden rounded-xl border border-green/70 p-[6px] shadow-2xl"
        style={{ backgroundColor: MAT }}
      >
        <div className="px-4 pt-2">
          <CategoryHeader versus={versus} />
          <VersusSide label="CROWD PICK" side={versus.yours} accent={GREEN} labelColor={GREEN} pctColor={GREEN} solo />
        </div>
        <PagerNav onPrev={onPrev} onNext={onNext} paged={paged} />
      </div>
    );
  }

  const isRogue = versus.state === "rogue";
  const yoursAccent = isRogue ? ROGUE : NEUTRAL;
  const yoursBar = isRogue ? ROGUE : MUTED;
  const yoursLabel = isRogue ? "ROGUE PICK" : "YOUR PICK";

  return (
    <div
      onClick={stop}
      className="flex max-h-[92vh] w-full max-w-[820px] flex-col overflow-hidden rounded-xl border border-white/60 p-[6px] shadow-2xl"
      style={{ backgroundColor: MAT }}
    >
      <div className="px-2 pt-2 lg:px-4">
        <CategoryHeader versus={versus} />
        <div className="grid grid-cols-[1fr_auto_1fr] gap-2 lg:gap-5">
          <VersusSide label="CROWD FAVORITE" side={versus.crowd} accent={MUTED} labelColor={MUTED} pctColor={NEUTRAL} />
          <div className="relative flex items-center justify-center">
            <div className="absolute inset-y-0 w-0.5 bg-white/20" />
            <span className="relative z-10 flex h-9 w-9 items-center justify-center rounded-full border border-white/60 font-display text-[13px] tracking-[0.08em] text-muted lg:h-12 lg:w-12 lg:text-[16px]" style={{ backgroundColor: MAT }}>
              VS
            </span>
          </div>
          <VersusSide label={yoursLabel} side={versus.yours} accent={yoursBar} labelColor={yoursAccent} pctColor={yoursAccent} />
        </div>
      </div>
      <PagerNav onPrev={onPrev} onNext={onNext} paged={paged} />
    </div>
  );
}

function VersusSide({
  label,
  side,
  accent,
  labelColor,
  pctColor,
  solo = false,
}: {
  label: string;
  side: PickVersusSide;
  accent: string;
  labelColor: string;
  pctColor: string;
  solo?: boolean;
}) {
  const fill = Math.max(Math.min(side.pickPct, 100), 4);
  const headerClass = solo
    ? "flex items-baseline justify-between gap-3"
    : "flex flex-col gap-1.5 lg:flex-row lg:items-baseline lg:justify-between lg:gap-3";
  const numberGroupClass = solo ? "flex items-baseline gap-1.5" : "order-2 flex items-baseline gap-1.5 lg:order-none";
  const pctClass = solo
    ? "font-mono tabular-nums text-[26px] font-semibold leading-none lg:text-[30px]"
    : "font-mono tabular-nums text-[20px] font-semibold leading-none lg:text-[30px]";
  const labelClass = solo
    ? "shrink-0 whitespace-nowrap font-display text-[16px] leading-none tracking-[0.14em]"
    : "order-1 truncate font-display text-[13px] leading-none tracking-[0.14em] lg:order-none lg:shrink-0 lg:whitespace-nowrap lg:text-[16px]";
  return (
    <div className="flex min-w-0 flex-col gap-2.5 lg:gap-3">
      <div className="flex flex-col gap-2 px-1">
        <div className={headerClass}>
          <span className={numberGroupClass}>
            <span className={pctClass} style={{ color: pctColor }}>
              {pickPctLabel(side.pickPct)}
            </span>
            <span className="text-[11px] leading-none text-muted lg:text-[13px]">of votes</span>
          </span>
          <span className={labelClass} style={{ color: labelColor }}>
            {label}
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full" style={{ width: `${fill}%`, background: accent }} />
        </div>
      </div>
      <img
        src={side.imageUrl}
        alt={side.name}
        className={`mx-auto max-h-[58vh] w-auto rounded-[10px] ${solo ? "max-w-[200px] lg:max-w-full" : "max-w-full"}`}
      />
    </div>
  );
}

function PagerNav({
  onPrev,
  onNext,
  paged,
}: {
  onPrev?: () => void;
  onNext?: () => void;
  paged: boolean;
}) {
  if (!paged) return null;
  return (
    <div className="flex items-center justify-between px-3 py-3.5">
      <NavButton dir="prev" label="Prev Pick" onClick={onPrev} />
      <NavButton dir="next" label="Next Pick" onClick={onNext} />
    </div>
  );
}

function NavButton({ dir, label, onClick }: { dir: "prev" | "next"; label: string; onClick?: () => void }) {
  const chevron = (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={dir === "prev" ? "M15 18l-6-6 6-6" : "M9 6l6 6 -6 6"} />
    </svg>
  );
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`flex h-9 items-center gap-2 rounded border border-white/40 px-3 font-display text-[14px] tracking-[0.14em] text-text transition-colors ${
        onClick ? "hover:bg-white/10" : "opacity-30"
      }`}
    >
      {dir === "prev" && chevron}
      {label.toUpperCase()}
      {dir === "next" && chevron}
    </button>
  );
}

function CategoryHeader({ versus }: { versus: PickVersus }) {
  return (
    <div className="flex items-center justify-center gap-2 px-2 pb-3 pt-1.5 lg:gap-2.5 lg:pb-4">
      <SlotPip slotKey={versus.slotKey} size={20} />
      <span className="font-display text-[18px] leading-none tracking-[0.2em] text-text lg:text-[22px]">
        {versus.slotLabel.toUpperCase()}
      </span>
    </div>
  );
}
