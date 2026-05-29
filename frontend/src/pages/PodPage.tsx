import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { SectionLabel } from "../components/SectionLabel";
import { BackButton, MobilePageHeader, PrevNextNav } from "../components/PageNav";
import { useIsMobile } from "../lib/use-is-mobile";
import { PodTable, PodTableSkeleton } from "../components/pod/PodTable";
import { PlayerSeatPanel } from "../components/pod/PlayerSeatPanel";
import type { RoundOutcome } from "../components/pod/PlayerSeatPanel";
import { MobileSeatStack, MobileSeatStackSkeleton } from "../components/pod/MobileSeatStack";
import { DeckScreenshotModal } from "../components/pod/DeckScreenshotModal";
import {
  usePodEventBySlug,
  usePodEventMatches,
  usePodEventParticipants,
  usePodEventReplays,
  usePodEvents,
} from "../data/hooks";
import { cleanPodEventName, podDiscordName } from "../data/utils";
import type {
  PodEventParticipantRow,
  PodSeat,
} from "../types/leaderboard";

const TABLE_MAX_WIDE = 720;
const TABLE_MAX_SHRUNK = 640;
const ANIMATION_MS = 500;
const CHROME_OFFSET = 260;

function compareParticipants(a: PodEventParticipantRow, b: PodEventParticipantRow): number {
  const ap = a.placement ?? Number.MAX_SAFE_INTEGER;
  const bp = b.placement ?? Number.MAX_SAFE_INTEGER;
  if (ap !== bp) return ap - bp;
  return a.displayName.localeCompare(b.displayName);
}

function assignSeats(rows: PodEventParticipantRow[]): PodSeat[] {
  const haveRealSeats = rows.some((r) => r.seatIndex != null);
  if (haveRealSeats) {
    return rows
      .slice()
      .filter((r) => r.seatIndex != null)
      .sort((a, b) => (a.seatIndex as number) - (b.seatIndex as number))
      .map((row) => ({
        ...row,
        seatIndex: row.seatIndex as number,
        discordName: podDiscordName(row),
      }));
  }
  const ordered = rows.slice().sort(compareParticipants);
  return ordered.map((row, i) => ({
    ...row,
    seatIndex: i,
    discordName: podDiscordName(row),
  }));
}

export function PodPage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const preselectName = searchParams.get("player");
  const isMobile = useIsMobile();
  const [selectedSeat, setSelectedSeat] = useState<number | null>(null);
  const [highlightedSeat, setHighlightedSeat] = useState<number | null>(null);
  const [highlightedRound, setHighlightedRound] = useState<number | null>(null);
  const [highlightedOutcome, setHighlightedOutcome] = useState<RoundOutcome | null>(null);
  const [animateLayout, setAnimateLayout] = useState(false);
  const [deckTarget, setDeckTarget] = useState<PodSeat | null>(null);

  const handleRoundHover = (seat: number | null, round: number | null, outcome: RoundOutcome | null) => {
    setHighlightedSeat(seat);
    setHighlightedRound(round);
    setHighlightedOutcome(outcome);
  };

  const handleSelectSeat = (seat: number | null) => {
    if (seat == null && isMobile) return;
    setSelectedSeat(seat);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (seat == null) {
          next.delete("player");
        } else {
          const participant = seats.find((p) => p.seatIndex === seat);
          if (participant) next.set("player", participant.discordName);
          else next.delete("player");
        }
        return next;
      },
      { replace: true },
    );
  };

  const { data: event, isLoading: eventLoading } = usePodEventBySlug(slug);
  const eventId = event?.eventId;
  const { data: participantRows, isLoading: participantsLoading } = usePodEventParticipants(eventId);
  const { data: matches, isLoading: matchesLoading } = usePodEventMatches(eventId);
  const { data: replays, isLoading: replaysLoading } = usePodEventReplays(eventId);
  const { data: setEvents } = usePodEvents(event?.setCode);

  const { prevSlug, nextSlug } = useMemo(() => {
    if (!setEvents || !event) return { prevSlug: null, nextSlug: null };
    const nowMs = Date.now();
    const started = setEvents.filter(
      (e) => e.championDisplayName || new Date(e.eventTime).getTime() <= nowMs,
    );
    const idx = started.findIndex((e) => e.eventId === event.eventId);
    if (idx < 0) return { prevSlug: null, nextSlug: null };
    return {
      prevSlug: idx > 0 ? started[idx - 1].slug : null,
      nextSlug: idx < started.length - 1 ? started[idx + 1].slug : null,
    };
  }, [setEvents, event]);
  const carryQuery = preselectName ? `?player=${encodeURIComponent(preselectName)}` : "";
  const prevTo = prevSlug ? `/pods/${prevSlug}${carryQuery}` : null;
  const nextTo = nextSlug ? `/pods/${nextSlug}${carryQuery}` : null;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      const t = e.target;
      if (t instanceof HTMLElement) {
        if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return;
      }
      if (e.key === "ArrowLeft" && prevTo) {
        e.preventDefault();
        navigate(prevTo);
      } else if (e.key === "ArrowRight" && nextTo) {
        e.preventDefault();
        navigate(nextTo);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prevTo, nextTo, navigate]);

  const seats = useMemo<PodSeat[]>(
    () => (participantRows ? assignSeats(participantRows) : []),
    [participantRows],
  );

  const participantsBySeatName = useMemo(() => {
    const m = new Map<string, PodSeat>();
    for (const s of seats) m.set(s.displayName, s);
    return m;
  }, [seats]);

  const selectedParticipant =
    selectedSeat == null ? null : seats.find((p) => p.seatIndex === selectedSeat) ?? null;

  const shellRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const [displayParticipant, setDisplayParticipant] = useState<PodSeat | null>(selectedParticipant);

  useLayoutEffect(() => {
    const shell = shellRef.current;
    const content = contentRef.current;
    if (!shell || !content) return;
    let restoreTimeout: number | null = null;
    const apply = () => {
      shell.style.overflowY = "hidden";
      shell.style.height = `${content.offsetHeight + 2}px`;
      if (restoreTimeout !== null) clearTimeout(restoreTimeout);
      restoreTimeout = window.setTimeout(() => {
        shell.style.overflowY = "";
      }, 320);
    };
    apply();
    const obs = new ResizeObserver(apply);
    obs.observe(content);
    return () => {
      obs.disconnect();
      if (restoreTimeout !== null) clearTimeout(restoreTimeout);
    };
  }, []);

  useEffect(() => {
    if (selectedParticipant) {
      setDisplayParticipant(selectedParticipant);
      return;
    }
    const t = setTimeout(() => setDisplayParticipant(null), ANIMATION_MS);
    return () => clearTimeout(t);
  }, [selectedParticipant]);

  useEffect(() => {
    if (!event || animateLayout) return;
    const id = window.requestAnimationFrame(() => setAnimateLayout(true));
    return () => window.cancelAnimationFrame(id);
  }, [event, animateLayout]);

  const [preselectChecked, setPreselectChecked] = useState(false);

  useEffect(() => {
    setPreselectChecked(false);
    setSelectedSeat(null);
  }, [slug]);

  useEffect(() => {
    if (preselectChecked) return;
    if (seats.length === 0) return;
    let target: PodSeat | undefined;
    if (preselectName) {
      const lower = preselectName.toLowerCase();
      target =
        seats.find((p) => p.discordName === preselectName) ??
        seats.find((p) => p.displayName === preselectName) ??
        seats.find((p) => p.discordName.toLowerCase() === lower) ??
        seats.find((p) => p.displayName.toLowerCase() === lower) ??
        seats.find((p) => p.placement === 1) ??
        seats[0];
    } else if (isMobile) {
      target = seats.find((p) => p.placement === 1) ?? seats[0];
    }
    if (target) setSelectedSeat(target.seatIndex);
    setPreselectChecked(true);
  }, [seats, preselectName, isMobile, preselectChecked]);

  const preselectPending = (!!preselectName || isMobile) && !preselectChecked;

  if (eventLoading || (event && participantsLoading) || (event && preselectPending)) {
    if (isMobile) {
      return (
        <div className="bg-bg text-text min-h-screen flex flex-col">
          <MobilePageHeader
            backTo="/pods"
            prevTo={null}
            nextTo={null}
            prevAriaLabel="Previous pod"
            nextAriaLabel="Next pod"
          />
          <MobileSeatStackSkeleton />
        </div>
      );
    }
    return (
      <div className="bg-bg text-text h-screen flex flex-col overflow-hidden">
        <AppHeader subtitle="POD DRAFT BREAKDOWN" />
        <main className="flex-1 flex flex-col pl-4 pr-4 md:pl-10 md:pr-12 lg:pr-14 pb-10 min-h-0">
          <div className="pt-5 pb-2 flex items-center justify-between gap-4 shrink-0">
            <BackButton to="/pods" label="BACK TO POD DRAFTS" inline />
          </div>
          {preselectName ? (
            <div className="flex-1 flex items-stretch min-h-0 py-3">
              <div className="flex items-center min-w-0 shrink-0 py-8 md:py-12 justify-end" style={{ width: "55%" }}>
                <PodTableSkeleton
                  maxWidth={`min(${TABLE_MAX_SHRUNK}px, calc(100vh - ${CHROME_OFFSET}px))`}
                />
              </div>
              <div className="min-w-0 shrink-0 self-start max-h-full" style={{ width: "45%" }}>
                <PodPanelSkeleton />
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center min-h-0 py-3">
              <PodTableSkeleton
                maxWidth={`min(${TABLE_MAX_WIDE}px, calc(100vh - ${CHROME_OFFSET}px))`}
              />
            </div>
          )}
        </main>
      </div>
    );
  }

  if (!event) {
    return (
      <div className="bg-bg text-text min-h-screen">
        <AppHeader subtitle="POD DRAFTS" />
        <main className="px-6 md:px-10 py-16 max-w-[720px]">
          <SectionLabel className="mb-3">Not found</SectionLabel>
          <h1 className="font-display text-text" style={{ fontSize: 36, letterSpacing: "0.04em" }}>
            No pod matched <span className="text-muted">"{slug}"</span>.
          </h1>
          <p className="text-muted mt-4">
            <Link to="/pods" className="text-green hover:underline">
              Back to pod drafts
            </Link>
          </p>
        </main>
      </div>
    );
  }

  const eventLabel = cleanPodEventName(event.name, event.setCode).toUpperCase();
  const open = selectedParticipant !== null;
  const tableMaxPx = open ? TABLE_MAX_SHRUNK : TABLE_MAX_WIDE;
  const loadedMatches = matches ?? [];
  const loadedReplays = replays ?? [];
  const auxLoading = matchesLoading || replaysLoading;

  if (isMobile) {
    return (
      <div className="bg-bg text-text min-h-screen flex flex-col">
        <MobilePageHeader
          backTo="/pods"
          prevTo={prevTo}
          nextTo={nextTo}
          prevAriaLabel="Previous pod"
          nextAriaLabel="Next pod"
        />
        <MobileSeatStack
          participants={seats}
          participantsBySeatName={participantsBySeatName}
          matches={loadedMatches}
          replays={loadedReplays}
          selectedSeat={selectedSeat}
          onSelect={handleSelectSeat}
          onShowDeck={setDeckTarget}
          eventLabel={eventLabel}
          setCode={event.setCode}
          formatLabel={event.formatLabel}
        />
        {deckTarget && (
          <DeckScreenshotModal
            participant={{
              eventId: deckTarget.eventId,
              displayName: deckTarget.discordName,
              participantDisplayName: deckTarget.displayName,
              deckColors: deckTarget.deckColors,
              deckScreenshotUrl: deckTarget.deckScreenshotUrl,
              deckScreenshotCaption: deckTarget.deckScreenshotCaption,
              record: deckTarget.record,
            }}
            onClose={() => setDeckTarget(null)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="bg-bg text-text h-screen flex flex-col overflow-hidden">
      <AppHeader subtitle="POD DRAFT BREAKDOWN" />

      <main className="flex-1 flex flex-col pl-4 pr-4 md:pl-10 md:pr-12 lg:pr-14 pb-10 min-h-0">
        <div className="pt-5 pb-2 flex items-center justify-between gap-4 shrink-0">
          <BackButton to="/pods" label="BACK TO POD DRAFTS" inline />
          <PrevNextNav
            prevTo={prevTo}
            nextTo={nextTo}
            prevAriaLabel="Previous pod"
            nextAriaLabel="Next pod"
          />
        </div>

        <div className="flex-1 flex items-stretch min-h-0 py-3">
          <div
            className={`flex items-center min-w-0 shrink-0 py-8 md:py-12 ${open ? "justify-end" : "justify-center"}`}
            style={{
              width: open ? "55%" : "100%",
              transition: animateLayout ? `width ${ANIMATION_MS}ms ease-out` : "none",
            }}
          >
            <PodTable
              participants={seats}
              selectedSeat={selectedSeat}
              highlightedSeat={highlightedSeat}
              highlightedRound={highlightedRound}
              highlightedOutcome={highlightedOutcome}
              onSelect={handleSelectSeat}
              onShowDeck={setDeckTarget}
              eventLabel={eventLabel}
              setCode={event.setCode}
              formatLabel={event.formatLabel}
              date={event.eventDate}
              maxWidth={`min(${tableMaxPx}px, calc(100vh - ${CHROME_OFFSET}px))`}
            />
          </div>
          <div
            className="min-w-0 shrink-0 self-start max-h-full"
            style={{
              width: open ? "45%" : "0%",
              opacity: open ? 1 : 0,
              transition: animateLayout
                ? `width ${ANIMATION_MS}ms ease-out, opacity ${ANIMATION_MS - 80}ms ease-out`
                : "none",
            }}
          >
            <div
              ref={shellRef}
              className="pod-panel-shell bg-surface border border-border max-h-full overflow-y-auto overflow-x-hidden themed-scrollbar"
            >
              <div ref={contentRef} style={{ minWidth: 360 }}>
                {displayParticipant && (
                  <PlayerSeatPanel
                    key={displayParticipant.displayName}
                    participant={displayParticipant}
                    participantsBySeatName={participantsBySeatName}
                    matches={loadedMatches}
                    replays={loadedReplays}
                    onRoundHover={handleRoundHover}
                    onShowDeck={setDeckTarget}
                  />
                )}
                {displayParticipant && auxLoading && (
                  <div className="px-5 py-2 text-muted text-[12px] font-body">
                    Loading matches & replays…
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
      {deckTarget && (
        <DeckScreenshotModal
          participant={{
            eventId: deckTarget.eventId,
            displayName: deckTarget.discordName,
            participantDisplayName: deckTarget.displayName,
            deckColors: deckTarget.deckColors,
            deckScreenshotUrl: deckTarget.deckScreenshotUrl,
            deckScreenshotCaption: deckTarget.deckScreenshotCaption,
            record: deckTarget.record,
          }}
          onClose={() => setDeckTarget(null)}
        />
      )}
    </div>
  );
}

function PodPanelSkeleton() {
  return (
    <div className="pod-panel-shell bg-surface border border-border max-h-full overflow-hidden">
      <div style={{ minWidth: 360 }}>
        <div className="flex items-center gap-4 px-4 md:px-5 xl:px-8 py-7 border-b border-border">
          <div className="w-[60px] h-[60px] bg-surface2 animate-pulse shrink-0" />
          <div className="min-w-0 flex-1 flex flex-col gap-2">
            <div className="h-7 w-2/3 bg-surface2 animate-pulse" />
            <div className="h-4 w-1/3 bg-surface2 animate-pulse" />
          </div>
          <div className="flex flex-col gap-2 shrink-0">
            <div className="h-[34px] w-[140px] bg-surface2 animate-pulse" />
            <div className="h-[34px] w-[140px] bg-surface2 animate-pulse" />
          </div>
        </div>
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="border-b border-border last:border-b-0 px-4 md:px-5 xl:px-8 py-3 flex items-center gap-3">
            <div className="h-[52px] w-[72px] bg-surface2 animate-pulse" />
            <div className="h-5 w-8 bg-surface2 animate-pulse" />
            <div className="h-5 flex-1 bg-surface2 animate-pulse" />
            <div className="h-[34px] w-[120px] bg-surface2 animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  );
}

