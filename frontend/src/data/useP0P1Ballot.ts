import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import {
  useP0P1Ballots,
  useP0P1Cards,
  useP0P1PickStats,
  useP0P1Picks,
  useP0P1Ratings,
  useUpsertP0P1Pick,
  useDeleteAllP0P1Picks,
  useSets,
} from "./hooks";
import { P0P1_SET_CODE as SET_CODE, P0P1_VOTING_DEADLINE as VOTING_DEADLINE, P0P1_SCORING_DATE as SCORING_DATE, SLOTS } from "./p0p1Slots";
import { useLocalP0P1Picks, setLocalPick, clearLocalPicks, getLocalPicks } from "./localPicks";
import { p0p1DevEnabled, p0p1Now, useP0P1DevPreset, type P0P1DevPreset } from "./p0p1DevState";
import { syntheticBallotsFromStats } from "./p0p1DevBallots";
import type { AuthUser } from "../auth/AuthContext";
import type { Card, P0P1BallotRow, P0P1PickStat, SlotKey } from "../types/p0p1";
import type { P0P1Phase, RatingsSnapshot } from "./p0p1Results";

const ADVANCE_BEAT_MS = 260;

export function useP0P1Ballot() {
  const { user: authUser, loading: authLoading, signIn } = useAuth();
  const devPreset = useP0P1DevPreset();
  const devActive = p0p1DevEnabled && devPreset !== "live";
  const useServerPicks = Boolean(authUser);
  const { data: cards } = useP0P1Cards(SET_CODE);
  const { data: serverPicks } = useP0P1Picks(useServerPicks ? SET_CODE : undefined);
  const localPicks = useLocalP0P1Picks(SET_CODE);
  const upsertPick = useUpsertP0P1Pick(SET_CODE);
  const clearAll = useDeleteAllP0P1Picks(SET_CODE);
  const [editingSlotKey, setEditingSlotKey] = useState<SlotKey | null>(null);

  const syncDone = useRef(false);
  useEffect(() => {
    if (!useServerPicks || !serverPicks || syncDone.current) return;
    syncDone.current = true;
    const local = getLocalPicks(SET_CODE);
    if (local.length === 0) return;
    const serverSlots = new Set(serverPicks.map((p) => p.slot));
    const toSync = local.filter((p) => !serverSlots.has(p.slot));
    for (const p of toSync) {
      upsertPick.mutate({ slot: p.slot, cardName: p.cardName });
    }
    clearLocalPicks(SET_CODE);
  }, [authUser, serverPicks, upsertPick]);

  const activePicks = authLoading ? undefined : useServerPicks ? serverPicks : localPicks;
  const dataReady = Boolean(cards) && activePicks !== undefined;

  const persistPick = useCallback(
    (slot: SlotKey, cardName: string) => {
      if (useServerPicks) {
        upsertPick.mutate({ slot, cardName });
      } else {
        setLocalPick(SET_CODE, slot, cardName);
      }
    },
    [useServerPicks, upsertPick],
  );

  const handleClearAll = useCallback(() => {
    if (useServerPicks) {
      clearAll.mutate();
    } else {
      clearLocalPicks(SET_CODE);
    }
  }, [useServerPicks, clearAll]);

  const cardsByName = useMemo(() => {
    if (!cards) return new Map<string, Card>();
    return new Map(cards.map((c) => [c.name, c]));
  }, [cards]);

  const picksBySlot = useMemo(() => {
    if (!activePicks) return new Map<string, string>();
    return new Map(activePicks.map((v) => [v.slot, v.cardName]));
  }, [activePicks]);

  const pickedCards = useMemo(() => new Set(picksBySlot.values()), [picksBySlot]);

  const pickedSlotLabels = useMemo(() => {
    const labels = new Map<string, string>();
    for (const slot of SLOTS) {
      const name = picksBySlot.get(slot.key);
      if (name) labels.set(name, slot.label);
    }
    return labels;
  }, [picksBySlot]);

  const pickedExcept = useCallback(
    (slotKey: SlotKey) => {
      const own = picksBySlot.get(slotKey);
      if (!own) return pickedCards;
      const rest = new Set(pickedCards);
      rest.delete(own);
      return rest;
    },
    [pickedCards, picksBySlot],
  );

  const isPastDeadline = p0p1Now() > VOTING_DEADLINE.getTime();
  const isPastScoringDate = p0p1Now() >= SCORING_DATE.getTime();
  const { data: pickStats } = useP0P1PickStats(SET_CODE, isPastDeadline);
  const { data: ratingsSnapshot, error: ratingsError } = useP0P1Ratings(SET_CODE);

  useEffect(() => {
    if (ratingsError) console.warn("P0P1 ratings fetch failed", ratingsError);
  }, [ratingsError]);

  const devViewPreset = devActive ? devPreset : "live";
  const user = applyDevUser(authUser, devViewPreset);
  const effectivePicksBySlot = applyDevPicks(picksBySlot, pickStats, devViewPreset);
  const resultsDataReady = Boolean(ratingsSnapshot && cards && pickStats);
  const midwayDataReady = resultsDataReady && ratingsSnapshot?.phase === "midway";
  const phase = deriveP0P1Phase(isPastDeadline, isPastScoringDate, ratingsSnapshot, resultsDataReady, devViewPreset);

  const devFinal = devActive && phase === "final";
  const { data: fetchedBallots } = useP0P1Ballots(SET_CODE, phase === "final" && !devFinal);
  // In dev presets, synthesize ballots from the live pick stats instead of
  // fetching — the public_p0p1_ballots view may not exist yet in the target DB
  const ballots = useMemo<P0P1BallotRow[] | undefined>(() => {
    if (!devFinal) return fetchedBallots;
    return pickStats ? syntheticBallotsFromStats(pickStats, SET_CODE) : undefined;
  }, [devFinal, fetchedBallots, pickStats]);

  // In dev results presets, append a ballot row for the viewer so findUserBallot
  // always resolves regardless of which picks the viewer has selected.
  const effectiveBallots = useMemo<P0P1BallotRow[] | undefined>(() => {
    if (!devActive || phase !== "final" || !ballots || effectivePicksBySlot.size === 0) {
      return ballots;
    }
    const youRows: P0P1BallotRow[] = [];
    for (const [slot, cardName] of effectivePicksBySlot) {
      youRows.push({
        setCode: SET_CODE,
        ballotId: 0,
        name: user?.username ?? "You",
        avatarUrl: user?.avatarUrl ?? null,
        slot: slot as SlotKey,
        cardName,
      });
    }
    return [...ballots, ...youRows];
  }, [devActive, phase, ballots, effectivePicksBySlot, user]);

  const scoringFilled = SLOTS.filter((s) => effectivePicksBySlot.has(s.key)).length;
  const isComplete = scoringFilled === SLOTS.length;
  const hasParticipated = isPastDeadline && Boolean(user) && scoringFilled > 0;

  const defaultSlotKey = useMemo(
    () => SLOTS.find((s) => !picksBySlot.has(s.key))?.key ?? SLOTS[0].key,
    [picksBySlot],
  );
  const activeSlotKey = editingSlotKey ?? defaultSlotKey;
  const activeSlot = SLOTS.find((s) => s.key === activeSlotKey)!;

  const nextUnfilledSlot = useCallback(
    (afterKey: SlotKey) => {
      const idx = SLOTS.findIndex((s) => s.key === afterKey);
      if (idx === -1) return afterKey;
      for (let i = 1; i < SLOTS.length; i++) {
        const candidate = SLOTS[(idx + i) % SLOTS.length];
        if (!picksBySlot.has(candidate.key)) return candidate.key;
      }
      return afterKey;
    },
    [picksBySlot],
  );

  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => clearTimeout(advanceTimer.current ?? undefined), []);

  const selectAdvance = useCallback(
    (slot: SlotKey, cardName: string) => {
      persistPick(slot, cardName);
      clearTimeout(advanceTimer.current ?? undefined);
      advanceTimer.current = setTimeout(() => setEditingSlotKey(nextUnfilledSlot(slot)), ADVANCE_BEAT_MS);
    },
    [persistPick, nextUnfilledSlot],
  );

  const selectAndClose = useCallback(
    (slot: SlotKey, cardName: string) => {
      persistPick(slot, cardName);
      setEditingSlotKey(null);
    },
    [persistPick],
  );

  const { data: allSets } = useSets();
  const p0p1Sets = useMemo(() => allSets?.filter((s) => s.code === SET_CODE), [allSets]);

  return {
    cards,
    cardsByName,
    dataReady,
    resultsDataReady,
    midwayDataReady,
    user,
    authLoading,
    signIn,
    picksBySlot: effectivePicksBySlot,
    pickedExcept,
    pickedSlotLabels,
    scoringFilled,
    isComplete,
    isPastDeadline,
    hasParticipated,
    pickStats,
    ratingsSnapshot,
    phase,
    ballots: effectiveBallots,
    persistPick,
    handleClearAll,
    clearPending: useServerPicks ? clearAll.isPending : false,
    editingSlotKey,
    setEditingSlotKey,
    activeSlotKey,
    activeSlot,
    selectAdvance,
    selectAndClose,
    p0p1Sets,
  };
}

const FAKE_DEV_USER: AuthUser = {
  id: "dev-preview-user",
  discordId: "0",
  username: "DevPreview",
  avatarUrl: null,
};

function applyDevUser(authUser: AuthUser | null, preset: P0P1DevPreset): AuthUser | null {
  if (preset === "closedLoggedOut") return null;
  if (
    preset === "closedComplete" ||
    preset === "closedDidNotVote" ||
    preset === "midwayScoring" ||
    preset === "midwayDidNotVote" ||
    preset === "finalizing" ||
    preset === "finalScoring"
  ) return authUser ?? FAKE_DEV_USER;
  return authUser;
}

function applyDevPicks(
  picksBySlot: Map<string, string>,
  pickStats: P0P1PickStat[] | undefined,
  preset: P0P1DevPreset,
): Map<string, string> {
  if (preset === "closedLoggedOut" || preset === "closedDidNotVote" || preset === "midwayDidNotVote") {
    return new Map();
  }
  if (
    preset === "closedComplete" ||
    preset === "midwayScoring" ||
    preset === "finalizing" ||
    preset === "finalScoring"
  ) {
    return picksBySlot.size > 0 ? picksBySlot : topPickPerSlot(pickStats);
  }
  return picksBySlot;
}

function topPickPerSlot(pickStats: P0P1PickStat[] | undefined): Map<string, string> {
  const topBySlot = new Map<string, P0P1PickStat>();
  for (const stat of pickStats ?? []) {
    const current = topBySlot.get(stat.slot);
    if (!current || stat.pickCount > current.pickCount) topBySlot.set(stat.slot, stat);
  }
  const picks = new Map<string, string>();
  for (const [slot, stat] of topBySlot) picks.set(slot, stat.cardName);
  return picks;
}

function deriveP0P1Phase(
  isPastDeadline: boolean,
  isPastScoringDate: boolean,
  snapshot: RatingsSnapshot | undefined,
  dataPresent: boolean,
  devPreset: P0P1DevPreset,
): P0P1Phase {
  if (devPreset === "midwayScoring" || devPreset === "midwayDidNotVote") return "midway";
  if (devPreset === "finalizing") return "finalizing";
  if (devPreset === "finalScoring") return "final";
  if (
    devPreset === "closedLoggedOut" ||
    devPreset === "closedComplete" ||
    devPreset === "closedDidNotVote"
  ) return "postVoting";

  if (!isPastDeadline) return "voting";

  if (!isPastScoringDate) {
    if (snapshot?.phase && dataPresent) {
      if (snapshot.phase === "final") {
        console.warn("P0P1 ratings fixture is marked final before the scoring date");
      }
      return snapshot.phase;
    }
    return "postVoting";
  }

  if (snapshot?.phase === "final" && dataPresent) return "final";
  return "finalizing";
}
