import React from "react";
import { cn } from "../lib/utils";

// LLU brand mark — the user-supplied logo PNG. Bypasses Vite's asset pipeline
// by living in /public so the public URL is deterministic across dev / prod.
export function ALogo({ size = 32 }: { size?: number }) {
  return (
    <img
      src="/leaderboard/llu-logo-transparent.png"
      alt="Limited Level-Ups"
      style={{ height: size, width: "auto" }}
      className="block"
    />
  );
}

// Wordmark — Bebas Neue stack of "LIMITED LEVEL-UPS" + a coloured subtitle.
export function AWordmark({
  size = "md",
  subtitle = "LEADERBOARD",
}: {
  size?: "sm" | "md" | "lg";
  subtitle?: string;
}) {
  const s =
    size === "sm" ? { lg: 12, sm: 8 } :
    size === "lg" ? { lg: 28, sm: 12 } :
    { lg: 18, sm: 9 };
  return (
    <div className="flex flex-col font-display" style={{ lineHeight: 0.95 }}>
      <span className="text-text tracking-[0.1em]" style={{ fontSize: s.lg }}>
        LIMITED LEVEL-UPS
      </span>
      <span className="text-green tracking-[0.32em] mt-[3px]" style={{ fontSize: s.sm }}>
        {subtitle}
      </span>
    </div>
  );
}

// Avatar with chamfered corners. When `avatarUrl` is null (the default at launch
// per spec §"Avatar plumbing"), falls back to two-letter initials.
export function AAvatar({
  displayName,
  avatarUrl,
  size = 36,
  green = false,
}: {
  displayName: string;
  avatarUrl?: string | null;
  size?: number;
  green?: boolean;
}) {
  const initials = displayName
    .split(/[\s\-_().]+/)
    .filter(Boolean)
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const clip = "polygon(8% 0, 100% 0, 100% 92%, 92% 100%, 0 100%, 0 8%)";
  if (avatarUrl) {
    return (
      <img
        src={avatarUrl}
        alt={displayName}
        width={size}
        height={size}
        className="block shrink-0 object-cover"
        style={{ clipPath: clip }}
      />
    );
  }
  return (
    <div
      className={cn(
        "bg-surface2 border flex items-center justify-center font-display tracking-[0.05em] shrink-0",
        green ? "border-green text-green" : "border-border2 text-text",
      )}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.45,
        clipPath: clip,
      }}
    >
      {initials}
    </div>
  );
}


// Trophy glyph — the marquee stat in this community (spec).
export function Trophy({
  size = 12,
  color,
  className,
}: {
  size?: number;
  color?: string;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      className={className ? `shrink-0 ${className}` : "shrink-0"}
      style={color ? { color } : undefined}
      aria-hidden="true"
    >
      <path
        d="M4 2h8v3a4 4 0 0 1-8 0V2zm-2 1h2v2a4 4 0 0 1-2-2zm10 0h2a4 4 0 0 1-2 2V3zM6 9h4v2H9v2h2v1H5v-1h2v-2H6V9z"
        fill={color ?? "currentColor"}
      />
    </svg>
  );
}

// Round-pts — the spec's score is whole points in display.
export const fmtPts = (n: number) => Math.round(n).toLocaleString("en-US");

// Set keyrune glyph wrapper (uses keyrune.css from index.html).
// Reserves a square box of `size` so swapping codes doesn't reflow neighbours
const KEYRUNE_OVERRIDES: Record<string, string> = {
  CUBE: "pz1",
};

export function keyruneClass(code: string): string {
  return KEYRUNE_OVERRIDES[code] ?? code.toLowerCase();
}

// Custom pod cube formats have no Keyrune glyph of their own; fall back to the generic cube symbol.
export function setGlyphCode(set: { code: string; custom?: boolean }): string {
  return set.custom ? "CUBE" : set.code;
}

export function SetGlyph({ code, size = 18 }: { code: string; size?: number }) {
  return (
    <span
      className="inline-flex items-center justify-center shrink-0 overflow-visible"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <i
        className={`ss ss-${keyruneClass(code)} text-white`}
        style={{ fontSize: size, lineHeight: 1 }}
      />
    </span>
  );
}
