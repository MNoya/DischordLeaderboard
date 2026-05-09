import React from "react";
import { cn } from "../lib/utils";

// The all-caps muted display-font caption used throughout the UI ("FORMAT
// BREAKDOWN", "DRAFT LOG", "TOP ARCHETYPES", etc).

export function SectionLabel({
  children,
  size = 11,
  letterSpacing = "0.22em",
  color,
  className,
  style,
}: {
  children: React.ReactNode;
  size?: number;
  letterSpacing?: string;
  color?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      className={cn("font-display text-muted", className)}
      style={{
        fontSize: size,
        letterSpacing,
        ...(color ? { color } : null),
        ...style,
      }}
    >
      {children}
    </div>
  );
}
