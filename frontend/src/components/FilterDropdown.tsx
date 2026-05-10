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

export function FilterDropdown({
  label,
  value,
  options,
  onChange,
  variant = "desktop",
  renderValue,
  renderOption,
}: {
  label: string;
  value: string;
  options: FilterOption[];
  onChange: (next: string) => void;
  variant?: "desktop" | "mobile";
  renderValue?: (option: FilterOption) => React.ReactNode;
  renderOption?: (option: FilterOption) => React.ReactNode;
}) {
  const isMobile = variant === "mobile";
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

  return (
    <div ref={ref} className={cn("relative", isMobile ? "flex-1 min-w-0" : "")}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex items-center gap-2 w-full bg-transparent border border-border2 font-display text-text cursor-pointer transition-colors hover:bg-surface",
          isMobile
            ? "px-2.5 py-1.5 text-[13px] tracking-[0.12em]"
            : "px-3.5 py-1.5 min-w-[220px] text-[13px] tracking-[0.14em]",
          open && "bg-surface",
        )}
      >
        <span
          className={cn(
            "text-muted tracking-[0.22em]",
            isMobile ? "text-[10px]" : "text-[11px]",
          )}
        >
          {label}
        </span>
        <span className="flex items-center gap-1.5 min-w-0 truncate">
          {renderValue ? renderValue(selected) : selected.label}
        </span>
        <span className="flex-1" />
        <span className={cn("text-muted", isMobile ? "text-[10px]" : "text-[10px]")}>
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open && (
        <div
          className="absolute left-0 top-[calc(100%+4px)] min-w-full w-max max-w-[calc(100vw-24px)] bg-surface border border-border2 z-20 shadow-lg"
          role="listbox"
        >
          {options.map((o, i) => {
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
                  "w-full text-left flex items-center gap-2 font-display cursor-pointer transition-colors whitespace-nowrap",
                  isMobile
                    ? "px-2.5 py-[9px] text-[13px] tracking-[0.1em]"
                    : "px-3.5 py-2 text-[13px] tracking-[0.08em]",
                  i > 0 && "border-t border-border",
                  isSelected ? "bg-surface2 text-text" : "bg-transparent text-text hover:bg-surface2",
                )}
              >
                {renderOption ? renderOption(o) : o.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
