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
  compact = false,
  menuAlign = "left",
  openOnHover = false,
  square = false,
  triggerClassName,
}: {
  sets: SetSummary[];
  activeCode: string;
  glyphCode: string;
  label: string;
  isMobile: boolean;
  loading?: boolean;
  onChange: (code: string) => void;
  compact?: boolean;
  menuAlign?: "left" | "right" | "center" | "side-right";
  openOnHover?: boolean;
  square?: boolean;
  triggerClassName?: string;
}) {
  const [open, setOpen] = React.useState(false);
  const [locked, setLocked] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const ref = React.useRef<HTMLDivElement>(null);
  const glyphSize = compact ? 20 : isMobile ? 26 : 38;
  const labelSize = compact ? "text-[18px]" : "text-[17px] md:text-[30px]";

  const close = () => {
    setOpen(false);
    setLocked(false);
  };

  React.useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  React.useEffect(() => {
    if (!open) {
      setQuery("");
    }
  }, [open]);

  if (!loading && sets.length <= 1) {
    return (
      <span className="flex items-center gap-2 md:gap-3 min-w-0">
        <SetGlyph code={glyphCode} size={glyphSize} />
        <span className="flex-1 min-w-0 truncate font-display tracking-[0.06em] text-[17px] md:text-[30px]">{label}</span>
      </span>
    );
  }

  const hasOptions = sets.length > 1;
  const sideRight = menuAlign === "side-right";
  const searchable = sets.length > 7;
  const trimmed = query.trim().toLowerCase();
  const filtered = trimmed
    ? sets.filter((s) => s.code.toLowerCase().includes(trimmed) || s.name.toLowerCase().includes(trimmed))
    : sets;

  const onButtonClick = () => {
    if (openOnHover) {
      if (locked) {
        close();
      } else {
        setLocked(true);
        setOpen(true);
      }
      return;
    }
    setOpen((o) => !o);
  };

  return (
    <div
      ref={ref}
      className="relative min-w-0"
      onMouseEnter={openOnHover ? () => setOpen(true) : undefined}
      onMouseLeave={openOnHover && !locked ? () => setOpen(false) : undefined}
    >
      <button
        type="button"
        disabled={!hasOptions}
        onClick={onButtonClick}
        aria-expanded={open}
        className={cn(
          "group flex max-w-full min-w-0 items-center border transition-colors",
          square ? "" : "rounded-md",
          compact ? "h-7 gap-1.5 px-2" : "gap-2 px-3 py-1.5 md:gap-3",
          open
            ? "border-green text-green"
            : "border-border2 text-text",
          hasOptions && !open && "cursor-pointer hover:border-green hover:text-green",
          triggerClassName,
        )}
      >
        <SetGlyph code={glyphCode} size={glyphSize} />
        <span className={cn("flex-1 min-w-0 truncate font-display tracking-[0.06em]", labelSize)}>{label}</span>
        <span
          className={cn(
            "shrink-0 transition-transform",
            compact ? "text-[12px]" : "text-[14px] md:text-[18px]",
            open && !sideRight && "rotate-180",
          )}
        >
          {sideRight ? (open ? "▸" : "▾") : "▾"}
        </span>
      </button>

      {open && (
        <div
          className={cn(
            "absolute z-30 flex max-h-[min(60vh,400px)] w-max max-w-[80vw] flex-col overflow-hidden border border-border2 bg-surface shadow-xl",
            square ? "" : "rounded-md",
            menuAlign === "side-right"
              ? "left-full top-0"
              : menuAlign === "right"
                ? "right-0 top-[calc(100%+6px)]"
                : menuAlign === "center"
                  ? "left-1/2 -translate-x-1/2 top-[calc(100%+6px)]"
                  : "left-1 top-[calc(100%+6px)] min-w-full",
          )}
        >
          {searchable && (
            <div className="shrink-0 border-b border-border p-1.5">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search sets…"
                className="w-full rounded-sm border border-border bg-surface2 px-2 py-1 font-body text-[13px] text-text placeholder:text-muted outline-none focus:border-green"
              />
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {filtered.map((s) => {
              const active = s.code === activeCode;
              return (
                <button
                  key={s.code}
                  type="button"
                  onClick={() => {
                    onChange(s.code);
                    close();
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
                    <span className={cn("text-[10px] tracking-[0.18em]", active ? "text-green" : "text-muted")}>
                      LIVE
                    </span>
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
            {filtered.length === 0 && (
              <div className="px-3.5 py-3 font-body text-[13px] text-muted">No sets match</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
