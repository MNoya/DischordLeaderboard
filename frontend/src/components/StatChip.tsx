import React from "react";
import { cn } from "../lib/utils";

// Compact label + value tile used in the player profile stat strip and the
// (mobile) hero. `accent` paints the value green for the headline POINTS metric.

export function StatChip({
  label,
  value,
  accent = false,
  mono = true,
}: {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col items-center text-center py-[7px] px-[6px] bg-surface border border-border min-w-0 overflow-hidden">
      <span className="text-[9px] tracking-[0.16em] text-muted font-display whitespace-nowrap">
        {label}
      </span>
      <span
        className={cn(
          "text-[16px] font-semibold mt-0.5 whitespace-nowrap",
          mono && "mono",
          accent ? "text-green" : "text-text",
        )}
      >
        {value}
      </span>
    </div>
  );
}
