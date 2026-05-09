import React from "react";
import { cn } from "../lib/utils";

// Standard sidebar card surface — the pattern used by `LeaderboardSidebar` and
// `ArchetypeSidebar` for "TOP ARCHETYPES", "RECENT TROPHIES", etc. Children are
// arranged with `border-t border-border` between siblings via the parent's
// own logic; this just owns the surface + padding.

export function SurfaceCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={cn("bg-surface px-4 py-3.5", className)}>{children}</div>;
}
