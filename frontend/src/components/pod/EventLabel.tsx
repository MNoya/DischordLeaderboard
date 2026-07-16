import type { ReactNode } from "react";

import { podSlotName } from "../../data/utils";
import type { PodEventSummary } from "../../types/leaderboard";

const SPLIT_RE = /(#\d+|\bmock\b)/gi;
const HIGHLIGHT_RE = /^(?:#\d+|mock)$/i;

// The pod row title: green execution-ordered `#N` (absent until the pod runs), the slot phrase, and a
// muted `Table N` qualifier for the second table onward. The date sits in the row's own date box.
export function PodEventTitle({ event }: { event: PodEventSummary }): ReactNode {
  const slot = podSlotName(event.name, event.setCode).toUpperCase();
  const tableIndex = event.tableIndex ?? 1;
  return (
    <>
      {event.ordinal != null && <span className="text-green">#{event.ordinal} </span>}
      {slot}
      {tableIndex > 1 && <span className="text-muted"> - TABLE {tableIndex}</span>}
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
