import React from "react";
import { SetGlyph } from "./Brand";
import { cn } from "../lib/utils";
import type { SetSummary } from "../types/leaderboard";

// Desktop set switcher — chamfered chip per set, bright green for active.
export function SetSwitcherDesktop({
  sets,
  activeCode,
  onChange,
}: {
  sets: SetSummary[];
  activeCode: string;
  onChange: (code: string) => void;
}) {
  return (
    <div className="flex gap-1.5">
      {sets.map((s) => {
        const active = s.code === activeCode;
        return (
          <button
            key={s.code}
            onClick={() => onChange(s.code)}
            className={cn(
              "py-2.5 pl-[18px] pr-[22px] font-display border flex items-center gap-2.5 min-w-[100px] cursor-pointer transition-colors",
              active
                ? "bg-green text-bg border-green"
                : "bg-transparent text-text border-border2 hover:bg-surface",
            )}
            style={{ clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)" }}
          >
            <i
              className={`ss ss-${s.code.toLowerCase()}`}
              style={{ fontSize: 22, color: active ? "#0a0c10" : "#e6ecf5", lineHeight: 1 }}
              aria-hidden="true"
            />
            <span className="text-[18px] tracking-[0.06em] leading-none">{s.code}</span>
          </button>
        );
      })}
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
