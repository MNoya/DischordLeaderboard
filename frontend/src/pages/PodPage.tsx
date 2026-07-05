import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { DraftReviewMOCS, type ReviewSeatInfo } from "../components/pod/review/DraftReviewMOCS";
import { SectionLabel } from "../components/SectionLabel";
import { BackButton, MobilePageHeader, PrevNextNav } from "../components/PageNav";
import { useIsLandscapePhone, useIsMobile } from "../lib/use-is-mobile";
import { PodTable, PodTableSkeleton } from "../components/pod/PodTable";
import { PlayerSeatPanel } from "../components/pod/PlayerSeatPanel";
import type { RoundOutcome } from "../components/pod/PlayerSeatPanel";
import { MobileSeatStack, MobileSeatStackSkeleton } from "../components/pod/MobileSeatStack";
import { DeckScreenshotModal, type DeckTab } from "../components/pod/DeckScreenshotModal";
import {
  usePodDraftArtifact,
  usePodEventBySlug,
  usePodEventMatches,
  usePodEventParticipants,
  usePodEventReplays,
  usePodEvents,
} from "../data/hooks";
import { resolveDeck } from "../data/draft-artifact";
import { cleanPodEventName, podDiscordName, podSeatName } from "../data/utils";
import type {
  PodEventParticipantRow,
  PodSeat,
} from "../types/leaderboard";

const TABLE_MAX_WIDE = 720;
const TABLE_MAX_SHRUNK = 640;
const ANIMATION_MS = 500;
const CHROME_OFFSET = 260;
const CHROME_OFFSET_LANDSCAPE = 84;
const PANEL_MIN_WIDTH = 360;
const PANEL_MIN_WIDTH_LANDSCAPE = 280;

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
  const isLandscapePhone = useIsLandscapePhone();
  const [selectedSeat, setSelectedSeat] = useState<number | null>(null);
  const [highlightedSeat, setHighlightedSeat] = useState<number | null>(null);
  const [highlightedRound, setHighlightedRound] = useState<number | null>(null);
  const [highlightedOutcome, setHighlightedOutcome] = useState<RoundOutcome | null>(null);
  const [animateLayout, setAnimateLayout] = useState(false);
  const [deckTarget, setDeckTarget] = useState<PodSeat | null>(null);
  const [deckInitialTab, setDeckInitialTab] = useState<DeckTab>("screenshot");

  const openDeck = (seat: PodSeat, tab: DeckTab = "screenshot") => {
    setDeckInitialTab(tab);
    setDeckTarget(seat);
  };

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
  const { data: draftArtifact } = usePodDraftArtifact(eventId);
  const deckTargetMainboard = useMemo(
    () => (draftArtifact && deckTarget ? resolveDeck(draftArtifact, deckTarget.seatIndex) : null),
    [draftArtifact, deckTarget],
  );
  const cycleDeck = (direction: number) => {
    if (!deckTarget || seats.length === 0) return;
    const index = seats.findIndex((s) => s.seatIndex === deckTarget.seatIndex);
    if (index === -1) return;
    setDeckTarget(seats[(index + direction + seats.length) % seats.length]);
  };
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

  const chromeOffset = isLandscapePhone ? CHROME_OFFSET_LANDSCAPE : CHROME_OFFSET;
  const panelMinWidth = isLandscapePhone ? PANEL_MIN_WIDTH_LANDSCAPE : PANEL_MIN_WIDTH;
  const mainClass = `flex-1 flex flex-col pl-4 pr-4 min-h-0 ${isLandscapePhone ? "pb-2" : "md:pl-10 md:pr-12 lg:pr-14 pb-10"}`;
  const tableColumnPad = isLandscapePhone ? "py-1" : "py-8 md:py-12";
  const contentRowPad = isLandscapePhone ? "py-1" : "py-3";
  const pageHeader = isLandscapePhone ? (
    <MobilePageHeader
      backTo="/pods"
      prevTo={prevTo}
      nextTo={nextTo}
      prevAriaLabel="Previous pod"
      nextAriaLabel="Next pod"
    />
  ) : (
    <AppHeader subtitle="POD DRAFT BREAKDOWN" />
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (deckTarget) return;
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
  }, [prevTo, nextTo, navigate, deckTarget]);

  const seats = useMemo<PodSeat[]>(() => {
    if (!participantRows) return [];
    const base = assignSeats(participantRows);
    if (!draftArtifact) return base;
    return base.map((s) => ({
      ...s,
      hasDeckList: resolveDeck(draftArtifact, s.seatIndex) !== null,
    }));
  }, [participantRows, draftArtifact]);

  const participantsBySeatName = useMemo(() => {
    const m = new Map<string, PodSeat>();
    for (const s of seats) m.set(podSeatName(s), s);
    return m;
  }, [seats]);

  const selectedParticipant =
    selectedSeat == null ? null : seats.find((p) => p.seatIndex === selectedSeat) ?? null;

  const [displayParticipant, setDisplayParticipant] = useState<PodSeat | null>(selectedParticipant);

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
    if (!participantRows) return;
    if (seats.length === 0) {
      setPreselectChecked(true);
      return;
    }
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
  }, [seats, preselectName, isMobile, preselectChecked, participantRows]);

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
        {pageHeader}
        <main className={mainClass}>
          {!isLandscapePhone && (
            <div className="pt-5 pb-2 flex items-center justify-between gap-4 shrink-0">
              <BackButton to="/pods" label="BACK TO POD DRAFTS" inline />
            </div>
          )}
          {preselectName ? (
            <div className={`flex-1 flex items-stretch min-h-0 ${contentRowPad}`}>
              <div className={`flex items-center min-w-0 shrink-0 justify-end ${tableColumnPad}`} style={{ width: "55%" }}>
                <PodTableSkeleton
                  maxWidth={`min(${TABLE_MAX_SHRUNK}px, calc(100vh - ${chromeOffset}px))`}
                />
              </div>
              <div className="min-w-0 shrink-0 self-start max-h-full" style={{ width: "45%" }}>
                <PodPanelSkeleton minWidth={panelMinWidth} />
              </div>
            </div>
          ) : (
            <div className={`flex-1 flex items-center justify-center min-h-0 ${contentRowPad}`}>
              <PodTableSkeleton
                maxWidth={`min(${TABLE_MAX_WIDE}px, calc(100vh - ${chromeOffset}px))`}
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
  const deckLogHref =
    draftArtifact && deckTarget ? `/pods/${event.slug}/${deckTarget.playerSlug ?? deckTarget.seatIndex}` : null;
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
          onShowDeck={openDeck}
          eventLabel={eventLabel}
          setCode={event.setCode}
          eventSlug={event.slug}
          hasDraftLog={!!draftArtifact}
          formatLabel={event.formatLabel}
          isMock={event.kind === "mock"}
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
              mainboard: deckTargetMainboard,
              record: deckTarget.record,
            }}
            initialTab={deckInitialTab}
            draftLogHref={deckLogHref}
            onClose={() => setDeckTarget(null)}
            onPrev={() => cycleDeck(-1)}
            onNext={() => cycleDeck(1)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="bg-bg text-text h-screen flex flex-col overflow-hidden">
      {pageHeader}

      <main className={mainClass}>
        {!isLandscapePhone && (
          <div className="pt-5 pb-2 flex items-center justify-between gap-4 shrink-0">
            <BackButton to="/pods" label="BACK TO POD DRAFTS" inline />
            <PrevNextNav
              prevTo={prevTo}
              nextTo={nextTo}
              prevAriaLabel="Previous pod"
              nextAriaLabel="Next pod"
            />
          </div>
        )}

        <div className={`flex-1 flex items-stretch min-h-0 ${contentRowPad}`}>
          <div
            className={`flex items-center min-w-0 shrink-0 ${tableColumnPad} ${open ? "justify-end" : "justify-center"}`}
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
              onShowDeck={openDeck}
              eventLabel={eventLabel}
              eventSlug={event.slug}
              hasDraftLog={!!draftArtifact}
              setCode={event.setCode}
              formatLabel={event.formatLabel}
              date={event.eventDate}
              maxWidth={`min(${tableMaxPx}px, calc(100vh - ${chromeOffset}px))`}
            />
          </div>
          <div
            className="min-w-0 shrink-0 self-start max-h-full flex flex-col min-h-0"
            style={{
              width: open ? "45%" : "0%",
              opacity: open ? 1 : 0,
              transition: animateLayout
                ? `width ${ANIMATION_MS}ms ease-out, opacity ${ANIMATION_MS - 80}ms ease-out`
                : "none",
            }}
          >
            <div className="pod-panel-shell bg-surface border border-border flex flex-col min-h-0 flex-1 overflow-hidden">
              <div className="flex flex-col min-h-0 flex-1" style={{ minWidth: panelMinWidth }}>
                {displayParticipant && (
                  <PlayerSeatPanel
                    key={displayParticipant.displayName}
                    participant={displayParticipant}
                    participantsBySeatName={participantsBySeatName}
                    matches={loadedMatches}
                    replays={loadedReplays}
                    setCode={event.setCode}
                    eventSlug={event.slug}
                    hasDraftLog={!!draftArtifact}
                    onRoundHover={handleRoundHover}
                    onShowDeck={openDeck}
                    isMock={event.kind === "mock"}
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
            mainboard: deckTargetMainboard,
            record: deckTarget.record,
          }}
          initialTab={deckInitialTab}
          draftLogHref={deckLogHref}
          onClose={() => setDeckTarget(null)}
          onPrev={() => cycleDeck(-1)}
          onNext={() => cycleDeck(1)}
        />
      )}
    </div>
  );
}

export function PodDraftLogRoute() {
  const { slug, who, pack, pick } = useParams<{ slug: string; who?: string; pack?: string; pick?: string }>();
  const navigate = useNavigate();
  const { data: event, isLoading: eventLoading } = usePodEventBySlug(slug);
  const eventId = event?.eventId;
  const { data: participantRows, isLoading: participantsLoading } = usePodEventParticipants(eventId);
  const { data: artifact, isLoading: artifactLoading } = usePodDraftArtifact(eventId);

  const seats = useMemo(
    () => (participantRows ? assignSeats(participantRows) : []),
    [participantRows],
  );

  if (eventLoading || (event && (participantsLoading || artifactLoading))) {
    return <div className="fixed inset-0 z-50 bg-bg" />;
  }
  if (!event || !artifact) {
    return <Navigate to={`/pods/${slug ?? ""}`} replace />;
  }

  if (!who) {
    return <Navigate to={`/pods/${slug}`} replace />;
  }

  const resolved = resolveLogSeat(seats, who);
  const initialSeat = resolved != null && resolved < artifact.seats.length ? resolved : 0;
  const initialPack = pack ? Number(pack) - 1 : 0;
  const initialPick = pick ? Number(pick) - 1 : 0;
  const seatInfo: ReviewSeatInfo[] = seats.map((s) => ({
    seatIndex: s.seatIndex,
    displayName: s.discordName,
    participantDisplayName: s.displayName,
    avatarUrl: s.avatarUrl,
    deckColors: s.deckColors,
    deckScreenshotUrl: s.deckScreenshotUrl,
    deckScreenshotCaption: s.deckScreenshotCaption,
    record: s.record,
  }));

  const current = resolved != null ? seats.find((s) => s.seatIndex === resolved) : null;
  const backHref = `/pods/${slug}${current ? `?player=${encodeURIComponent(current.discordName)}` : ""}`;

  return (
    <DraftReviewMOCS
      artifact={artifact}
      meta={{ setCode: event.setCode, name: event.name }}
      initialSeat={initialSeat}
      initialPack={initialPack}
      initialPick={initialPick}
      onClose={() => navigate(backHref)}
      backHref={backHref}
      onNavigate={(seatIndex, p, pk) => {
        const target = seats.find((s) => s.seatIndex === seatIndex);
        if (target) {
          navigate(`/pods/${slug}/${seatIdentifier(target)}/${p + 1}/${pk + 1}`, { replace: true });
        }
      }}
      eventId={event.eventId}
      seatInfo={seatInfo}
    />
  );
}

function seatIdentifier(seat: PodSeat): string {
  return seat.playerSlug ?? String(seat.seatIndex);
}

function resolveLogSeat(seats: PodSeat[], who: string): number | null {
  const bySlug = seats.find((s) => s.playerSlug === who);
  if (bySlug) {
    return bySlug.seatIndex;
  }
  const n = Number(who);
  if (Number.isInteger(n) && seats.some((s) => s.seatIndex === n)) {
    return n;
  }
  return null;
}

function PodPanelSkeleton({ minWidth = PANEL_MIN_WIDTH }: { minWidth?: number }) {
  return (
    <div className="pod-panel-shell bg-surface border border-border max-h-full overflow-hidden">
      <div style={{ minWidth }}>
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

