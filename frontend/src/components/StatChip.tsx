import React from "react";
import { Info } from "./Icons";
import { cn } from "../lib/utils";

// Compact label + value tile used in the player profile mobile hero strip.
// `accent` paints the value green for the headline POINTS metric. Mirrors the
// desktop StatStrip font choice (Bebas Neue) for visual parity.

export function StatChip({
  label,
  value,
  accent = false,
  onClick,
  buttonRef,
}: {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
  onClick?: () => void;
  buttonRef?: React.RefObject<HTMLButtonElement>;
}) {
  const baseCls =
    "flex flex-col items-center text-center py-[7px] px-[6px] bg-surface border border-border min-w-0 overflow-hidden";
  const inner = (
    <>
      <span className="text-[10.5px] tracking-[0.16em] leading-none text-muted font-display whitespace-nowrap relative inline-block">
        {label}
        {onClick && (
          <span
            aria-hidden="true"
            className="absolute top-1/2 -translate-y-1/2 ml-1 leading-none"
            style={{ left: "100%" }}
          >
            <Info size={11} className="text-muted" />
          </span>
        )}
      </span>
      <span
        className={cn(
          "font-display tracking-[0.02em] text-[20px] leading-none mt-1 whitespace-nowrap tabular-nums",
          accent ? "text-green" : "text-text",
        )}
      >
        {value}
      </span>
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        ref={buttonRef}
        onClick={onClick}
        className={cn(baseCls, "cursor-pointer hover:bg-surface2 transition-colors")}
      >
        {inner}
      </button>
    );
  }
  return <div className={baseCls}>{inner}</div>;
}
