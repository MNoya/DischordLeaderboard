import React, { useEffect, useRef, useState } from "react";
import { cn } from "../lib/utils";

// Custom click-to-open dropdown — same family as SetSwitcherMobile so styled
// content (color swatches, mana pips, etc) renders cleanly in both the closed
// trigger and the open option list. Replaces the previous native <select>
// which couldn't host React content in its menu.
//
// Both `renderValue` and `renderOption` are optional and default to the option's
// plain label.

export interface FilterOption {
  value: string;
  label: string;
}

const SEARCH_THRESHOLD = 8;

export function FilterDropdown({
  label,
  value,
  options,
  onChange,
  variant = "desktop",
  renderValue,
  renderOption,
  searchable,
  searchPlaceholder = "Search…",
  triggerClassName,
  className,
}: {
  label?: string;
  value: string;
  options: FilterOption[];
  onChange: (next: string) => void;
  variant?: "desktop" | "mobile";
  renderValue?: (option: FilterOption) => React.ReactNode;
  renderOption?: (option: FilterOption) => React.ReactNode;
  searchable?: boolean;
  searchPlaceholder?: string;
  triggerClassName?: string;
  className?: string;
}) {
  const isMobile = variant === "mobile";
  const selected = options.find((o) => o.value === value) ?? options[0];
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const showSearch = searchable ?? options.length > SEARCH_THRESHOLD;

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }
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

  const trimmed = query.trim().toLowerCase();
  const filtered = trimmed
    ? options.filter(
        (o) => o.label.toLowerCase().includes(trimmed) || o.value.toLowerCase().includes(trimmed),
      )
    : options;

  return (
    <div ref={ref} className={cn("relative", isMobile ? "flex-1 min-w-0" : "", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-2 w-full bg-transparent border border-border2 font-display text-text cursor-pointer transition-colors hover:bg-surface",
          isMobile
            ? "px-2.5 py-1.5 text-[15px] tracking-[0.1em]"
            : "px-3.5 py-1.5 min-w-[220px] text-[15px] tracking-[0.12em]",
          open && "bg-surface",
          triggerClassName,
        )}
      >
        {label ? (
          <span className={cn("text-muted tracking-[0.22em]", isMobile ? "text-[11px]" : "text-[12px]")}>
            {label}
          </span>
        ) : null}
        <span className="flex items-center gap-1.5 min-w-0 truncate">
          {renderValue ? renderValue(selected) : selected.label}
        </span>
        <span className="flex-1" />
        <span className="text-muted text-[11px]">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div
          className="absolute left-0 top-[calc(100%+4px)] min-w-full w-max max-w-[calc(100vw-24px)] flex max-h-[min(60vh,420px)] flex-col bg-surface border border-border2 z-20 shadow-lg"
          role="listbox"
        >
          {showSearch && (
            <div className="shrink-0 border-b border-border p-1.5">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full bg-bg border border-border px-2.5 py-1.5 font-body text-[14px] text-text placeholder:text-dim outline-none focus:border-green"
              />
            </div>
          )}
          <div className="menu-scrollbar min-h-0 flex-1 overflow-y-auto">
            {filtered.map((o, i) => {
              const isSelected = o.value === value;
              return (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  role="option"
                  aria-selected={isSelected}
                  className={cn(
                    "w-full text-left flex items-center gap-2 border-l-2 font-display cursor-pointer transition-colors whitespace-nowrap",
                    isMobile
                      ? "px-2.5 py-2.5 text-[15px] tracking-[0.08em]"
                      : "px-3.5 py-2.5 text-[15px] tracking-[0.06em]",
                    i > 0 && "border-t border-border",
                    isSelected
                      ? "border-l-green bg-surface2 text-green"
                      : "border-l-transparent bg-transparent text-text hover:bg-surface2",
                  )}
                >
                  {renderOption ? renderOption(o) : o.label}
                </button>
              );
            })}
            {filtered.length === 0 && (
              <div className="px-3.5 py-3 font-body text-[14px] text-muted">No matches</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
