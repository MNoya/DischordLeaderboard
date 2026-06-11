import React from "react";
import { SetGlyph, setGlyphCode } from "./Brand";
import { cn } from "../lib/utils";
import { TIER_LIST_PREVIEW_SETS } from "../data/constants";
import type { SetSummary } from "../types/leaderboard";

export function TierSetDropdown({
  sets,
  activeCode,
  glyphCode,
  label,
  isMobile,
  loading = false,
  onChange,
}: {
  sets: SetSummary[];
  activeCode: string;
  glyphCode: string;
  label: string;
  isMobile: boolean;
  loading?: boolean;
  onChange: (code: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const glyphSize = isMobile ? 26 : 38;

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

  if (!loading && sets.length <= 1) {
    return (
      <span className="flex items-center gap-2 md:gap-3 min-w-0">
        <SetGlyph code={glyphCode} size={glyphSize} />
        <span className="flex-1 min-w-0 truncate text-[17px] md:text-[30px]">{label}</span>
      </span>
    );
  }

  const hasOptions = sets.length > 1;

  return (
    <div ref={ref} className="relative min-w-0">
      <button
        type="button"
        disabled={!hasOptions}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "group flex max-w-full min-w-0 items-center gap-2 rounded-md border px-3 py-1.5 transition-colors md:gap-3",
          open
            ? "border-green text-green"
            : "border-border2 text-text",
          hasOptions && !open && "cursor-pointer hover:border-green hover:text-green",
        )}
      >
        <SetGlyph code={glyphCode} size={glyphSize} />
        <span className="flex-1 min-w-0 truncate text-[17px] md:text-[30px]">{label}</span>
        <span className={cn("shrink-0 text-[14px] md:text-[18px] transition-transform", open && "rotate-180")}>▾</span>
      </button>

      {open && (
        <div className="absolute left-1 top-[calc(100%+6px)] z-30 w-max min-w-full max-w-[80vw] overflow-hidden rounded-md border border-border2 bg-surface shadow-xl">
          {sets.map((s) => {
            const active = s.code === activeCode;
            return (
              <button
                key={s.code}
                type="button"
                onClick={() => {
                  onChange(s.code);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-3 border-l-2 px-3.5 py-2.5 text-left font-display tracking-[0.06em] transition-colors",
                  active
                    ? "border-green bg-surface2 text-green"
                    : "border-transparent text-text hover:bg-surface2 hover:text-green",
                )}
              >
                <SetGlyph code={setGlyphCode(s)} size={24} />
                <span className="flex-1 truncate text-[17px] leading-none">{s.name.toUpperCase()}</span>
                {s.isActive ? (
                  <span className={cn("text-[10px] tracking-[0.18em]", active ? "text-green" : "text-muted")}>LIVE</span>
                ) : (
                  TIER_LIST_PREVIEW_SETS[s.code] && (
                    <span className="text-[10px] tracking-[0.18em]" style={{ color: "#cca54e" }}>
                      PREVIEW
                    </span>
                  )
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
