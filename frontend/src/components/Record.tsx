import React from "react";
import { cn } from "../lib/utils";

// Win–loss record renderer. Two visual modes:
//   <Record wins={67} losses={16} />               → tricolor: W green, "–" dim, L muted
//   <Record wins={67} losses={16} mono />          → single tone, both text-colored
//   <Record wins={7} losses={2} mono color={...}>  → single tone, custom color

export function Record({
  wins,
  losses,
  mono = false,
  color,
  separatorMargin = 0,
  className,
  style,
}: {
  wins: number;
  losses: number;
  mono?: boolean;
  color?: string;
  separatorMargin?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  if (mono) {
    return (
      <span
        className={cn(color ? "" : "text-text", className)}
        style={{ ...(color ? { color } : null), ...style }}
      >
        {wins}
        <span
          className="text-dim"
          style={separatorMargin ? { margin: `0 ${separatorMargin}px` } : undefined}
        >
          –
        </span>
        {losses}
      </span>
    );
  }
  return (
    <span className={className} style={style}>
      <span className="text-green">{wins}</span>
      <span className="text-dim">–</span>
      <span className="text-muted">{losses}</span>
    </span>
  );
}
