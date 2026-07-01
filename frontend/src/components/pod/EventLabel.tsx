import type { ReactNode } from "react";

const SPLIT_RE = /(#\d+|\bmock\b)/gi;
const HIGHLIGHT_RE = /^(?:#\d+|mock)$/i;

// Renders an event label with the placement token (`#N`) and the word "MOCK" in green; everything
// else stays as-is. Shared by the pod table medallion, the mobile stack, and the draft reviewer so
// the same words light up consistently.
export function highlightEventLabel(label: string): ReactNode {
  return label
    .split(SPLIT_RE)
    .map((part, i) => (HIGHLIGHT_RE.test(part) ? <span key={i} className="text-green">{part}</span> : part));
}
