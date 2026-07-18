import type { ReactNode } from "react";

import { podEventQualifier, podSlotName } from "../../data/utils";
import type { PodEventSummary } from "../../types/leaderboard";

const SPLIT_RE = /(#\d+|\bmock\b)/gi;
const HIGHLIGHT_RE = /^(?:#\d+|mock)$/i;

// Green execution-ordered `#N` (absent until the pod runs), the slot phrase, then a muted qualifier
export function PodEventTitle({ event }: { event: PodEventSummary }): ReactNode {
  const slot = podSlotName(event.name, event.setCode).toUpperCase();
  const qualifier = podEventQualifier(event).toUpperCase();
  return (
    <>
      {event.ordinal != null && <span className="text-green">#{event.ordinal} </span>}
      {slot}
      {qualifier && <span className="text-muted">{qualifier}</span>}
    </>
  );
}

// Renders an event label with the placement token (`#N`) and the word "MOCK" in green; everything
// else stays as-is. Shared by the pod table medallion, the mobile stack, and the draft reviewer so
// the same words light up consistently.
export function highlightEventLabel(label: string): ReactNode {
  return label
    .split(SPLIT_RE)
    .map((part, i) => (HIGHLIGHT_RE.test(part) ? <span key={i} className="text-green">{part}</span> : part));
}
