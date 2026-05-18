import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { SectionLabel } from "../components/SectionLabel";
import { BackButton, MobilePageHeader, PrevNextNav } from "../components/PageNav";
import { useIsMobile } from "../lib/use-is-mobile";
import { PodTable } from "../components/pod/PodTable";
import { PlayerSeatPanel } from "../components/pod/PlayerSeatPanel";
import { MobileSeatStack } from "../components/pod/MobileSeatStack";
import { podSos3Fixture, type PodParticipant } from "../data/fixtures/pod-sos-3";

const POD_FIXTURES = [podSos3Fixture];

const TABLE_MAX_WIDE = 720;
const TABLE_MAX_SHRUNK = 640;
const ANIMATION_MS = 500;
const CHROME_OFFSET = 260;

export function PodPage() {
  const { slug } = useParams<{ slug: string }>();
  const isMobile = useIsMobile();
  const [selectedSeat, setSelectedSeat] = useState<number | null>(null);
  const [highlightedSeat, setHighlightedSeat] = useState<number | null>(null);
  const [highlightedRound, setHighlightedRound] = useState<number | null>(null);
  const [highlightedWon, setHighlightedWon] = useState<boolean | null>(null);

  const handleRoundHover = (seat: number | null, round: number | null, won: boolean | null) => {
    setHighlightedSeat(seat);
    setHighlightedRound(round);
    setHighlightedWon(won);
  };

  const event = useMemo(() => POD_FIXTURES.find((p) => p.slug === slug) ?? null, [slug]);

  const participantsBySeatName = useMemo(() => {
    const m = new Map<string, PodParticipant>();
    if (event) for (const p of event.participants) m.set(p.displayName, p);
    return m;
  }, [event]);

  const selectedParticipant = selectedSeat == null || !event
    ? null
    : event.participants.find((p) => p.seatIndex === selectedSeat) ?? null;

  const [displayParticipant, setDisplayParticipant] = useState<PodParticipant | null>(selectedParticipant);
  useEffect(() => {
    if (selectedParticipant) {
      setDisplayParticipant(selectedParticipant);
      return;
    }
    const t = setTimeout(() => setDisplayParticipant(null), ANIMATION_MS);
    return () => clearTimeout(t);
  }, [selectedParticipant]);

  useEffect(() => {
    if (!isMobile || !event || selectedSeat !== null) return;
    const champion = event.participants.find((p) => p.placement === 1);
    if (champion) setSelectedSeat(champion.seatIndex);
  }, [isMobile, event, selectedSeat]);

  if (!event) {
    return (
      <div className="bg-bg text-text min-h-screen animate-fadeIn">
        <AppHeader subtitle="POD DRAFTS" />
        <main className="px-6 md:px-10 py-16 max-w-[720px]">
          <SectionLabel className="mb-3">Not found</SectionLabel>
          <h1 className="font-display text-text" style={{ fontSize: 36, letterSpacing: "0.04em" }}>
            No pod matched <span className="text-muted">"{slug}"</span>.
          </h1>
          <p className="text-muted mt-4">
            <Link to="/" className="text-green hover:underline">
              Back to the leaderboard
            </Link>
          </p>
        </main>
      </div>
    );
  }

  const podNumber = derivePodNumber(event.name);
  const open = selectedParticipant !== null;
  const tableMaxPx = open ? TABLE_MAX_SHRUNK : TABLE_MAX_WIDE;

  if (isMobile) {
    return (
      <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
        <MobilePageHeader
          backTo="/pods"
          prevTo={null}
          nextTo={null}
          prevAriaLabel="Previous pod"
          nextAriaLabel="Next pod"
        />
        <MobileSeatStack
          participants={event.participants}
          participantsBySeatName={participantsBySeatName}
          matches={event.matches}
          replays={event.replays}
          selectedSeat={selectedSeat}
          onSelect={setSelectedSeat}
          podNumber={podNumber}
          setCode={event.setCode}
        />
      </div>
    );
  }

  return (
    <div className="bg-bg text-text h-screen flex flex-col overflow-hidden animate-fadeIn">
      <AppHeader subtitle="POD DRAFT BREAKDOWN" />

      <main className="flex-1 flex flex-col pl-4 pr-4 md:pl-10 md:pr-12 lg:pr-14 pb-10 min-h-0">
        <div className="pt-5 pb-2 flex items-center justify-between gap-4 shrink-0">
          <BackButton to="/pods" label="BACK TO POD DRAFTS" inline />
          <PrevNextNav
            prevTo={null}
            nextTo={null}
            prevAriaLabel="Previous pod"
            nextAriaLabel="Next pod"
          />
        </div>

        <div className="flex-1 flex items-stretch min-h-0 py-3">
          <div
            className={`flex items-center min-w-0 shrink-0 py-8 md:py-12 ${open ? "justify-end" : "justify-center"}`}
            style={{
              width: open ? "55%" : "100%",
              transition: `width ${ANIMATION_MS}ms ease-out`,
            }}
          >
            <PodTable
              participants={event.participants}
              selectedSeat={selectedSeat}
              highlightedSeat={highlightedSeat}
              highlightedRound={highlightedRound}
              highlightedWon={highlightedWon}
              onSelect={setSelectedSeat}
              podNumber={podNumber}
              setCode={event.setCode}
              date={event.date}
              maxWidth={`min(${tableMaxPx}px, calc(100vh - ${CHROME_OFFSET}px))`}
            />
          </div>
          <div
            className="min-w-0 shrink-0 self-start max-h-full"
            style={{
              width: open ? "45%" : "0%",
              opacity: open ? 1 : 0,
              transition: `width ${ANIMATION_MS}ms ease-out, opacity ${ANIMATION_MS - 80}ms ease-out`,
            }}
          >
            <div
              className="pod-panel-shell bg-surface border border-border max-h-full overflow-y-auto overflow-x-hidden themed-scrollbar"
            >
              <div style={{ minWidth: 360 }}>
                {displayParticipant && (
                  <PlayerSeatPanel
                    key={displayParticipant.playerId}
                    participant={displayParticipant}
                    participantsBySeatName={participantsBySeatName}
                    matches={event.matches}
                    replays={event.replays}
                    onRoundHover={handleRoundHover}
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function derivePodNumber(name: string): number {
  const m = name.match(/#(\d+)/);
  return m ? Number(m[1]) : 1;
}
