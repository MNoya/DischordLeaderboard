import { useSyncExternalStore } from "react";
import { P0P1_SCORING_DATE } from "./p0p1Slots";

export type P0P1DevPreset =
  | "live"
  | "closedLoggedOut"
  | "closedComplete"
  | "closedDidNotVote";

export const P0P1_DEV_PRESETS: { value: P0P1DevPreset; label: string }[] = [
  { value: "live", label: "Live" },
  { value: "closedLoggedOut", label: "Closed · logged out" },
  { value: "closedComplete", label: "Closed · complete entry" },
  { value: "closedDidNotVote", label: "Closed · logged in, didn't vote" },
];

export const p0p1DevEnabled = import.meta.env.DEV && typeof window !== "undefined";

const STORAGE_KEY = "p0p1DevPreset";
const listeners = new Set<() => void>();

function readStored(): P0P1DevPreset {
  if (!p0p1DevEnabled) return "live";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  const valid = P0P1_DEV_PRESETS.some((p) => p.value === stored);
  return valid ? (stored as P0P1DevPreset) : "live";
}

let current = readStored();

export function setP0P1DevPreset(preset: P0P1DevPreset) {
  current = preset;
  window.localStorage.setItem(STORAGE_KEY, preset);
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function useP0P1DevPreset(): P0P1DevPreset {
  return useSyncExternalStore(subscribe, () => current, () => "live");
}

const DEV_RESULTS_REMAINING_MS = (20 * 24 + 1) * 60 * 60 * 1000;

export function p0p1Now(): number {
  if (p0p1DevEnabled && current !== "live") {
    return P0P1_SCORING_DATE.getTime() - DEV_RESULTS_REMAINING_MS;
  }
  return Date.now();
}
