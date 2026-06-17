import { useEffect, useRef, useState } from "react";
import { SetGlyph } from "./Brand";
import { CUBE_BASE, CUBE_LIFETIME, isCubeSeasonCode } from "../data/utils";
import { cn } from "../lib/utils";
import type { CubeSeason } from "../types/leaderboard";

const LIFETIME_LABEL = "LIFETIME";

// CUBE recurs every set; this picks which window the board scores over. LIFETIME
// is the all-time board (CUBE-ALL sentinel); each season is a virtual CUBE-<SET> code
// scoped to that set's release window. Seasons arrive newest-first from the view.
//
// The "hero" variant renders inline, matched to the set-hero date line so the CUBE
// header keeps a normal set's height; "mobile" is a tappable boxed trigger. Each
// option shows the set symbol — LIFETIME falls back to the generic cube glyph.
export function CubeSeasonSelector({
  activeSet,
  seasons,
  onSelect,
  variant = "hero",
}: {
  activeSet: string;
  seasons: CubeSeason[] | undefined;
  onSelect: (setCode: string) => void;
  variant?: "hero" | "mobile";
}) {
  const value = isCubeSeasonCode(activeSet) ? activeSet : CUBE_LIFETIME;
  const options = [
    { value: CUBE_LIFETIME, label: LIFETIME_LABEL, glyph: CUBE_BASE },
    ...(seasons ?? []).map((s) => ({ value: s.setCode, label: `${s.label} SEASON`, glyph: s.label })),
  ];
  const selected = options.find((o) => o.value === value) ?? options[0];
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
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

  const hero = variant === "hero";
  return (
    <div ref={ref} className={cn("relative", hero ? "" : "flex-1 min-w-0")}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center cursor-pointer transition-colors font-display leading-none",
          hero
            ? "gap-2 text-[20px] tracking-[0.04em] text-muted hover:text-text"
            : "w-full gap-2 bg-transparent border border-border2 text-text px-2.5 py-1.5 text-[15px] tracking-[0.12em] hover:bg-surface",
          !hero && open && "bg-surface",
        )}
      >
        <SetGlyph code={selected.glyph} size={hero ? 22 : 20} />
        <span className={cn(hero ? "text-text" : "")}>{selected.label}</span>
        {!hero && <span className="flex-1" />}
        <span className={cn("leading-none", hero ? "text-[11px]" : "text-[9px]")}>{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div
          className="absolute left-0 top-[calc(100%+4px)] w-max max-w-[calc(100vw-24px)] bg-surface border border-border2 z-50 shadow-lg"
          role="listbox"
        >
          {options.map((o, i) => {
            const isSelected = o.value === value;
            return (
              <button
                key={o.value}
                type="button"
                onClick={() => {
                  onSelect(o.value);
                  setOpen(false);
                }}
                role="option"
                aria-selected={isSelected}
                className={cn(
                  "w-full text-left flex items-center gap-2.5 font-display cursor-pointer transition-colors whitespace-nowrap px-3.5 py-2 text-[15px] tracking-[0.08em]",
                  i > 0 && "border-t border-border",
                  isSelected ? "bg-surface2 text-text" : "bg-transparent text-text hover:bg-surface2",
                )}
              >
                <SetGlyph code={o.glyph} size={20} />
                {o.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
