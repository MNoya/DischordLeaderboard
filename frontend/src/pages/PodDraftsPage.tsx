import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";

import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { SectionLabel } from "../components/SectionLabel";
import { HeroSection } from "../components/HeroSection";
import { MobilePageHeader } from "../components/PageNav";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { AAvatar, Trophy } from "../components/Brand";
import { Pips } from "../components/ManaPips";
import { RankBadge } from "../components/RankBadge";
import { Record } from "../components/Record";
import { useIsMobile } from "../lib/use-is-mobile";
import { fmtShortDate, winPct } from "../data/utils";
import {
  usePodEventParticipants,
  usePodEvents,
  usePodLeaderboard,
  usePodSetCodes,
  useSets,
} from "../data/hooks";
import type {
  PodEventParticipantRow,
  PodEventSummary,
  PodLeaderboardRow,
  SetSummary,
} from "../types/leaderboard";

const DEFAULT_SET = "SOS";

export function PodDraftsPage() {
  const isMobile = useIsMobile();
  const { data: allSets } = useSets();
  const { data: podSetCodes } = usePodSetCodes();

  const availableSets = useMemo<SetSummary[]>(() => {
    if (!allSets || !podSetCodes) return [];
    const codes = new Set(podSetCodes);
    return allSets.filter((s) => codes.has(s.code));
  }, [allSets, podSetCodes]);

  const [activeSet, setActiveSet] = useState<string>(DEFAULT_SET);
  useEffect(() => {
    if (availableSets.length === 0) return;
    if (!availableSets.find((s) => s.code === activeSet)) {
      setActiveSet(availableSets[0].code);
    }
  }, [availableSets, activeSet]);

  const { data: events } = usePodEvents(activeSet);
  const { data: leaderboard } = usePodLeaderboard(activeSet);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      {isMobile ? (
        <MobilePageHeader
          backTo="/"
          prevTo={null}
          nextTo={null}
          prevAriaLabel="Previous set"
          nextAriaLabel="Next set"
        />
      ) : (
        <AppHeader subtitle="POD DRAFTS" />
      )}

      <HeroSection className="px-4 md:px-10 pt-6 pb-6">
        <SectionLabel className="mb-2">Pod Drafts</SectionLabel>
        <div className="flex items-end justify-between gap-4 flex-wrap">
          <h1
            className="font-display text-text"
            style={{
              fontSize: "clamp(32px, 5vw, 56px)",
              letterSpacing: "0.04em",
              lineHeight: 0.95,
            }}
          >
            ALL RECORDED PODS
          </h1>
          {availableSets.length > 1 && (
            <div className="shrink-0">
              {isMobile ? (
                <SetSwitcherMobile
                  sets={availableSets}
                  activeCode={activeSet}
                  onChange={setActiveSet}
                />
              ) : (
                <SetSwitcherDesktop
                  sets={availableSets}
                  activeCode={activeSet}
                  onChange={setActiveSet}
                />
              )}
            </div>
          )}
        </div>
      </HeroSection>

      <main className="flex-1 px-4 md:px-10 pt-6 pb-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          <section>
            {leaderboard && leaderboard.length > 0 ? (
              <PodLeaderboardTable rows={leaderboard} isMobile={isMobile} />
            ) : (
              <EmptyHint>No player stats yet for {activeSet}.</EmptyHint>
            )}
          </section>

          <section>
            <SectionLabel className="mb-3">Events</SectionLabel>
            {events && events.length > 0 ? (
              <div className="flex flex-col gap-2">
                {events.map((e) => (
                  <EventRow key={e.eventId} event={e} />
                ))}
              </div>
            ) : (
              <EmptyHint>No pod drafts recorded yet for {activeSet}.</EmptyHint>
            )}
          </section>
        </div>
      </main>

      <Footer className="mt-auto px-4 md:px-10 py-4 md:pt-5 md:pb-3 shrink-0" />
    </div>
  );
}

function EventRow({ event }: { event: PodEventSummary }) {
  const [open, setOpen] = useState(false);
  const dateLabel = fmtShortDate(event.eventDate);
  return (
    <div className="bg-surface border border-border hover:border-border2 transition-colors">
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to={`/pods/${event.slug}`}
            className="font-display text-text hover:text-green no-underline transition-colors truncate"
            style={{ fontSize: 20, letterSpacing: "0.04em" }}
          >
            {event.name.toUpperCase()}
          </Link>
          <span className="text-dim">·</span>
          <span
            className="font-display text-muted tracking-[0.18em] uppercase shrink-0"
            style={{ fontSize: 11 }}
          >
            {dateLabel}
          </span>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {event.championDisplayName && (
            <div className="hidden md:flex items-center gap-2">
              <Trophy size={14} color="#ffc63a" />
              <span className="font-display text-text" style={{ fontSize: 16, letterSpacing: "0.03em" }}>
                {event.championDisplayName}
              </span>
              {event.championDeckColors && <Pips colors={event.championDeckColors} size={12} />}
            </div>
          )}
          <span
            className="font-display text-muted tracking-[0.18em] uppercase"
            style={{ fontSize: 11 }}
          >
            {event.participantCount} seats
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={open ? "Collapse standings" : "Expand standings"}
          className="bg-transparent border-0 p-1.5 cursor-pointer text-muted hover:text-text transition-colors"
        >
          <ChevronDown
            size={18}
            className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </button>
      </div>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
        aria-hidden={!open}
      >
        <div className="overflow-hidden">
          {open && <EventStandings event={event} />}
        </div>
      </div>
    </div>
  );
}

function EventStandings({ event }: { event: PodEventSummary }) {
  const { data: rows, isLoading } = usePodEventParticipants(event.eventId);
  const sorted = useMemo(() => {
    if (!rows) return [];
    return [...rows].sort((a, b) => {
      const ap = a.placement ?? 99;
      const bp = b.placement ?? 99;
      return ap - bp;
    });
  }, [rows]);
  return (
    <div className="px-4 pb-4 pt-1 border-t border-border">
      <div className="flex items-center justify-end mb-3">
        <Link
          to={`/pods/${event.slug}`}
          className="font-display text-muted hover:text-green tracking-[0.18em] uppercase no-underline transition-colors"
          style={{ fontSize: 11 }}
        >
          Full Breakdown →
        </Link>
      </div>
      {isLoading ? (
        <div className="text-muted text-[13px]">Loading standings…</div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {sorted.map((p) => (
            <StandingRow key={`${p.eventId}-${p.displayName}`} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function StandingRow({ p }: { p: PodEventParticipantRow }) {
  return (
    <div className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 px-2 py-1.5 bg-bg">
      {p.placement != null ? <RankBadge rank={p.placement} size="sm" /> : <span style={{ width: 32 }} />}
      <div className="flex items-center gap-2 min-w-0">
        {p.deckColors && <Pips colors={p.deckColors} size={12} />}
        {p.playerSlug ? (
          <Link
            to={`/player/${p.playerSlug}`}
            className="font-display text-text hover:text-green no-underline truncate"
            style={{ fontSize: 16, letterSpacing: "0.03em" }}
          >
            {p.displayName}
          </Link>
        ) : (
          <span className="font-display text-text truncate" style={{ fontSize: 16, letterSpacing: "0.03em" }}>
            {p.displayName}
          </span>
        )}
      </div>
      <span className="font-display tabular-nums text-muted" style={{ fontSize: 14, letterSpacing: "0.08em" }}>
        {p.record ?? "—"}
      </span>
      {p.draftLogUrl ? (
        <a
          href={p.draftLogUrl}
          target="_blank"
          rel="noreferrer noopener"
          className="font-display text-muted hover:text-green tracking-[0.16em] uppercase no-underline transition-colors"
          style={{ fontSize: 11 }}
        >
          Log →
        </a>
      ) : (
        <span style={{ width: 32 }} />
      )}
    </div>
  );
}

function PodLeaderboardTable({ rows, isMobile }: { rows: PodLeaderboardRow[]; isMobile: boolean }) {
  return (
    <div className="flex flex-col gap-[1.5px]">
      {!isMobile && <PodLeaderboardHeader />}
      {rows.map((r) => (
        <PodLeaderboardRowEl key={r.slug} row={r} isMobile={isMobile} />
      ))}
    </div>
  );
}

const POD_COLS_DESKTOP = "44px 1fr 70px 100px 110px 90px";
const POD_COLS_MOBILE = "20px 1fr 44px 50px";

function PodLeaderboardHeader() {
  return (
    <div
      className="grid items-center gap-x-3 px-2 py-2 text-muted font-display tracking-[0.18em] uppercase"
      style={{ gridTemplateColumns: POD_COLS_DESKTOP, fontSize: 11 }}
    >
      <span className="text-center">#</span>
      <span>Player</span>
      <span className="text-right">Trophies</span>
      <span className="text-right">Events</span>
      <span className="text-right">Record</span>
      <span className="text-right">Win %</span>
    </div>
  );
}

function PodLeaderboardRowEl({ row, isMobile }: { row: PodLeaderboardRow; isMobile: boolean }) {
  if (isMobile) {
    return (
      <div
        className="grid items-center gap-3 px-2 py-[9px] bg-transparent border-b border-border"
        style={{ gridTemplateColumns: POD_COLS_MOBILE }}
      >
        <span className="mono text-[12px] text-muted text-center">{row.rank}</span>
        <div className="flex items-center gap-2.5 min-w-0">
          <AAvatar displayName={row.displayName} avatarUrl={row.avatarUrl} size={26} />
          <Link
            to={`/player/${row.slug}`}
            className="font-display leading-none tracking-[0.04em] truncate no-underline text-text hover:text-green transition-colors"
            style={{ fontSize: 17 }}
          >
            {row.displayName.toUpperCase()}
          </Link>
        </div>
        <div className="text-right flex items-center justify-end gap-[3px]">
          <Trophy size={10} color="#ffc63a" />
          <span className="font-display tracking-[0.02em] tabular-nums text-[15px] leading-none">{row.trophies}</span>
        </div>
        <Record className="mono text-right text-[13px]" wins={row.wins} losses={row.losses} />
      </div>
    );
  }
  return (
    <div
      className="grid items-center gap-x-3 py-2.5 pl-2 pr-5 bg-surface hover:bg-surface2 transition-colors"
      style={{ gridTemplateColumns: POD_COLS_DESKTOP }}
    >
      <span className="mono text-[13px] text-muted text-center">{row.rank}</span>
      <div className="flex items-center gap-2.5 min-w-0">
        <AAvatar displayName={row.displayName} avatarUrl={row.avatarUrl} size={30} />
        <Link
          to={`/player/${row.slug}`}
          className="font-display leading-none tracking-[0.04em] truncate no-underline text-text hover:text-green transition-colors"
          style={{ fontSize: 18 }}
        >
          {row.displayName.toUpperCase()}
        </Link>
      </div>
      <div className="text-right flex items-center justify-end gap-1.5">
        <Trophy size={14} color="#ffc63a" />
        <span className="font-display tracking-[0.02em] tabular-nums text-[18px] leading-none">{row.trophies}</span>
      </div>
      <span className="mono text-right text-[13px] text-muted">{row.events}</span>
      <Record className="mono text-right text-[13px]" wins={row.wins} losses={row.losses} />
      <span className="mono text-right text-[13px] text-muted">{winPct(row.wins, row.losses)}%</span>
    </div>
  );
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-muted text-[13px] py-4 px-2 bg-surface border border-border">
      {children}
    </div>
  );
}
