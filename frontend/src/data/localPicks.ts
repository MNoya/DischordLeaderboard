import { useCallback, useSyncExternalStore } from "react";
import type { P0P1Pick, SlotKey } from "../types/p0p1";

function storageKey(setCode: string) {
  return `p0p1-picks-${setCode}`;
}

function readPicks(setCode: string): P0P1Pick[] {
  try {
    const raw = localStorage.getItem(storageKey(setCode));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writePicks(setCode: string, picks: P0P1Pick[]) {
  localStorage.setItem(storageKey(setCode), JSON.stringify(picks));
  window.dispatchEvent(new StorageEvent("storage", { key: storageKey(setCode) }));
}

export function setLocalPick(setCode: string, slot: SlotKey, cardName: string) {
  const picks = readPicks(setCode).filter((p) => p.slot !== slot);
  picks.push({ slot, cardName, lastUpdated: new Date().toISOString() });
  writePicks(setCode, picks);
}

export function clearLocalPicks(setCode: string) {
  localStorage.removeItem(storageKey(setCode));
  window.dispatchEvent(new StorageEvent("storage", { key: storageKey(setCode) }));
}

export function getLocalPicks(setCode: string): P0P1Pick[] {
  return readPicks(setCode);
}

export function useLocalP0P1Picks(setCode: string): P0P1Pick[] {
  const subscribe = useCallback(
    (onStoreChange: () => void) => {
      const key = storageKey(setCode);
      const handler = (e: StorageEvent) => {
        if (e.key === key || e.key === null) onStoreChange();
      };
      window.addEventListener("storage", handler);
      return () => window.removeEventListener("storage", handler);
    },
    [setCode],
  );

  const getSnapshot = useCallback(() => {
    return localStorage.getItem(storageKey(setCode)) ?? "";
  }, [setCode]);

  const raw = useSyncExternalStore(subscribe, getSnapshot);
  try {
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}
