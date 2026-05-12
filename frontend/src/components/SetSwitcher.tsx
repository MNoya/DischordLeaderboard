import React from "react";
import { SetGlyph } from "./Brand";
import { cn } from "../lib/utils";
import { useSetVisibleCap } from "../lib/use-is-mobile";
import type { SetSummary } from "../types/leaderboard";

function partitionSets(sets: SetSummary[], selectedCode: string, cap: number) {
  const sorted = [...sets].sort((a, b) => b.startDate.localeCompare(a.startDate));
  if (sorted.length <= cap) return { visible: sorted, overflow: [] };

  const liveCode = sorted.find((s) => s.isActive)?.code;
  const pinned = new Set<string>();
  if (liveCode) pinned.add(liveCode);
  pinned.add(selectedCode);

  const visible: SetSummary[] = [];
  for (const s of sorted) if (pinned.has(s.code)) visible.push(s);
  for (const s of sorted) {
    if (visible.length >= cap) break;
    if (!pinned.has(s.code)) visible.push(s);
  }
  visible.sort((a, b) => b.startDate.localeCompare(a.startDate));

  const visibleCodes = new Set(visible.map((s) => s.code));
  const overflow = sorted.filter((s) => !visibleCodes.has(s.code));
  return { visible, overflow };
}

export function SetSwitcherDesktop({
  sets,
  activeCode,
  onChange,
}: {
  sets: SetSummary[];
  activeCode: string;
  onChange: (code: string) => void;
}) {
  const cap = useSetVisibleCap(sets.length);
  const { visible, overflow } = partitionSets(sets, activeCode, cap);
  return (
    <div className="flex gap-1.5">
      {visible.map((s) => (
        <SetChip key={s.code} set={s} active={s.code === activeCode} onClick={() => onChange(s.code)} />
      ))}
      {overflow.length > 0 && (
        <SetOverflow sets={overflow} activeCode={activeCode} onChange={onChange} />
      )}
    </div>
  );
}

const CHAMFER = "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)";

function SetChip({
  set,
  active,
  onClick,
}: {
  set: SetSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group block cursor-pointer transition-colors"
      style={{
        clipPath: CHAMFER,
        background: active ? "#2ee85c" : "#3b4458",
        padding: 1,
        minHeight: 42,
      }}
    >
      <span
        className={cn(
          "flex items-center gap-2.5 min-w-[98px] pl-[17px] pr-[21px] font-display transition-colors h-full",
          active ? "bg-green text-bg" : "bg-surface text-text group-hover:bg-surface2",
        )}
        style={{ clipPath: CHAMFER, minHeight: 40 }}
      >
        <i
          className={`ss ss-${set.code.toLowerCase()}`}
          style={{ fontSize: 22, color: active ? "#0a0c10" : "#e6ecf5", lineHeight: 1 }}
          aria-hidden="true"
        />
        <span className="text-[20px] tracking-[0.06em] leading-none">{set.code}</span>
      </span>
    </button>
  );
}

function SetOverflow({
  sets,
  activeCode,
  onChange,
}: {
  sets: SetSummary[];
  activeCode: string;
  onChange: (code: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="group block cursor-pointer transition-colors"
        style={{
          clipPath: CHAMFER,
          background: "#3b4458",
          padding: 1,
          minHeight: 42,
        }}
      >
        <span
          className="flex items-center gap-2 min-w-[98px] pl-[17px] pr-[21px] font-display transition-colors h-full bg-surface text-text group-hover:bg-surface2"
          style={{ clipPath: CHAMFER, minHeight: 40 }}
        >
          <span className="text-[20px] tracking-[0.06em] leading-none">
            +{sets.length} {sets.length === 1 ? "SET" : "SETS"}
          </span>
          <span className="text-muted text-[12px] leading-none">▾</span>
        </span>
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+4px)] w-max bg-surface border border-border2 z-20">
          {sets.map((s) => (
            <button
              key={s.code}
              onClick={() => {
                onChange(s.code);
                setOpen(false);
              }}
              className={cn(
                "w-full py-[11px] px-3.5 flex items-center gap-3 border-b border-border text-text font-display tracking-[0.06em] cursor-pointer text-left transition-colors",
                s.code === activeCode ? "bg-surface2" : "bg-transparent hover:bg-surface2",
              )}
            >
              <SetGlyph code={s.code} size={22} />
              <span className="text-[20px] leading-none">{s.code}</span>
              <span className="text-muted text-[13px] tracking-[0.06em] whitespace-nowrap">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Mobile: a single button that opens a sheet of options.
export function SetSwitcherMobile({
  sets,
  activeCode,
  onChange,
}: {
  sets: SetSummary[];
  activeCode: string;
  onChange: (code: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const active = sets.find((s) => s.code === activeCode) ?? sets[0];
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full py-1.5 px-2.5 flex items-center gap-2 bg-transparent border border-border2 text-text font-display text-[13px] tracking-[0.12em] cursor-pointer"
      >
        <SetGlyph code={active.code} size={16} />
        <span>{active.code}</span>
        {active.isActive && (
          <span className="text-muted text-[10px] tracking-[0.18em]">· LIVE</span>
        )}
        <span className="flex-1" />
        <span className="text-muted text-[10px]">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] bg-surface border border-border2 z-20">
          {sets.map((s) => (
            <button
              key={s.code}
              onClick={() => {
                onChange(s.code);
                setOpen(false);
              }}
              className={cn(
                "w-full py-[9px] px-2.5 flex items-center gap-2 border-none border-b border-border text-text font-display text-[13px] tracking-[0.1em] cursor-pointer text-left transition-colors",
                s.code === activeCode ? "bg-surface2" : "bg-transparent hover:bg-surface2",
              )}
            >
              <SetGlyph code={s.code} size={16} />
              <span>{s.code}</span>
              <span className="text-muted text-[10px] tracking-[0.06em] flex-1">{s.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
