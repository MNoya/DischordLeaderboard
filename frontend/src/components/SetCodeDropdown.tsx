import React from "react";
import { cn } from "../lib/utils";
import { SetGlyph } from "./Brand";
import { ChevronDown } from "./Icons";
import type { SetSummary } from "../types/leaderboard";

const CHAMFER = "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)";

export function SetCodeDropdown({
  sets,
  activeCode,
  onChange,
  size = "md",
}: {
  sets: SetSummary[];
  activeCode: string;
  onChange: (code: string) => void;
  size?: "sm" | "md";
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

  const sorted = React.useMemo(
    () => [...sets].sort((a, b) => b.startDate.localeCompare(a.startDate)),
    [sets],
  );

  const isSm = size === "sm";
  const labelFs = isSm ? "text-[22px]" : "text-[26px]";
  const padL = isSm ? "pl-[14px]" : "pl-[16px]";
  const padR = isSm ? "pr-[18px]" : "pr-[20px]";
  const heightOuter = isSm ? 38 : 46;
  const heightInner = isSm ? 36 : 44;
  const glyphSize = isSm ? 26 : 32;

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((o) => !o)}
        className="group block cursor-pointer transition-colors"
        style={{
          clipPath: CHAMFER,
          background: "#3b4458",
          padding: 1,
          minHeight: heightOuter,
        }}
      >
        <span
          className={cn(
            "flex items-center gap-2 font-display tracking-[0.06em] transition-colors h-full bg-surface text-text group-hover:bg-surface2",
            padL,
            padR,
          )}
          style={{ clipPath: CHAMFER, minHeight: heightInner }}
        >
          <SetGlyph code={activeCode} size={glyphSize} />
          <span className={cn(labelFs, "leading-none")}>{activeCode}</span>
          <ChevronDown
            strokeWidth={2.5}
            className={cn("text-muted transition-transform", isSm ? "h-4 w-4" : "h-[18px] w-[18px]", open && "rotate-180")}
          />
        </span>
      </button>
      {open && (
        <div
          className="absolute top-[calc(100%+4px)] bg-surface border border-border2 z-30"
          style={{ left: 0, right: 8 }}
        >
          {sorted.map((s) => (
            <button
              key={s.code}
              onClick={() => {
                onChange(s.code);
                setOpen(false);
              }}
              className={cn(
                "w-full py-2 flex items-center gap-2 text-text font-display tracking-[0.06em] cursor-pointer text-left transition-colors border-b border-border pr-3",
                padL,
                s.code === activeCode ? "bg-surface2" : "bg-transparent hover:bg-surface2",
              )}
            >
              <SetGlyph code={s.code} size={glyphSize} />
              <span className={cn(labelFs, "leading-none")}>{s.code}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
