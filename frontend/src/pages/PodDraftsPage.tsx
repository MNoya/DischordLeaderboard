import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { TbCards } from "react-icons/tb";

import { AppHeader } from "../components/AppHeader";
import { Footer } from "../components/Footer";
import { SectionLabel } from "../components/SectionLabel";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { AAvatar, ArrowRight, SetGlyph, Trophy } from "../components/Brand";
import { DiscordIcon } from "../components/BrandIcons";
import { ChamferedButton } from "../components/ChamferedButton";
import { BREAKDOWN_CAPTION, DeckScreenshotModal } from "../components/pod/DeckScreenshotModal";
import { Pips } from "../components/ManaPips";
import { Record } from "../components/Record";
import {
  DEFAULT_SORT_NOSCORE,
  LeaderboardTable,
  sortRows,
  type LeaderboardTableRow,
  type SortKey,
  type SortState,
} from "../components/LeaderboardTable";
import { useIsMobile } from "../lib/use-is-mobile";
import { cn } from "../lib/utils";
import { cleanPodEventName, fmtRange, podDiscordName, stripDiscriminator, weekOfSet } from "../data/utils";
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
const MONTHS_CAL = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const DISCORD_GUILD_ID = "775371722065051658";

function parseMonthDay(iso: string): { month: string; day: number } {
  const m = parseInt(iso.slice(5, 7), 10);
  const d = parseInt(iso.slice(8, 10), 10);
  return { month: MONTHS_CAL[m - 1] ?? "", day: d };
}

function formatLocalTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(d);
}

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function formatCountdown(targetMs: number, nowMs: number): string {
  let secs = Math.max(0, Math.floor((targetMs - nowMs) / 1000));
  const days = Math.floor(secs / 86400);
  secs -= days * 86400;
  const hours = Math.floor(secs / 3600);
  secs -= hours * 3600;
  const minutes = Math.floor(secs / 60);
  const seconds = secs - minutes * 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  if (days > 0) return `${days}d ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function CountdownChip({ iso }: { iso: string }) {
  const targetMs = useMemo(() => new Date(iso).getTime(), [iso]);
  const now = useNow(1000);
  if (!Number.isFinite(targetMs)) return null;
  const remaining = targetMs - now;
  const label = remaining <= 0 ? "00:00:00" : formatCountdown(targetMs, now);
  return (
    <span
      className="font-mono text-text tabular-nums shrink-0 border border-border2 bg-surface2/40 px-2 py-1"
      style={{ fontSize: 13, lineHeight: 1, letterSpacing: "0.02em" }}
    >
      {label}
    </span>
  );
}

function toLeaderboardRow(r: PodLeaderboardRow): LeaderboardTableRow {
  return {
    setCode: r.setCode,
    slug: r.slug,
    displayName: r.displayName,
    avatarUrl: r.avatarUrl,
    rank: r.rank,
    trophies: r.trophies,
    events: r.events,
    wins: r.wins,
    losses: r.losses,
    lastCalculatedAt: r.lastFinishedAt ?? "",
  };
}

export function PodDraftsPage() {
  const isMobile = useIsMobile(1024);
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
  const setMeta = availableSets.find((s) => s.code === activeSet);

  const [sort, setSort] = useState<SortState>(DEFAULT_SORT_NOSCORE);
  const sortedLeaderboard = useMemo(() => {
    if (!leaderboard) return undefined;
    const adapted: LeaderboardTableRow[] = leaderboard.map(toLeaderboardRow);
    return sortRows(adapted, sort);
  }, [leaderboard, sort]);
  const onSort = (key: SortKey) => {
    setSort((cur) =>
      cur.key === key
        ? { key, dir: cur.dir === "desc" ? "asc" : "desc" }
        : { key, dir: "desc" },
    );
  };

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const { played, upcoming } = useMemo(() => {
    if (!events) return { played: [] as PodEventSummary[], upcoming: [] as PodEventSummary[] };
    const p: PodEventSummary[] = [];
    const u: PodEventSummary[] = [];
    for (const e of events) {
      if (!e.championDisplayName && e.eventDate > today) u.push(e);
      else p.push(e);
    }
    return { played: p, upcoming: u };
  }, [events, today]);

  usePodEventParticipants(played[0]?.eventId);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="POD DRAFTS" />

      {isMobile ? (
        <MobileSetStrip
          activeSet={activeSet}
          availableSets={availableSets}
          onSelectSet={setActiveSet}
        />
      ) : (
        <SetHero
          activeSet={activeSet}
          setMeta={setMeta}
          sets={availableSets}
          onSelectSet={setActiveSet}
        />
      )}

      <main className="flex-1 lg:px-5 lg:pb-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-6 lg:gap-y-8">
          <section className="order-2 lg:order-1">
            <SectionHeading
              label="STANDINGS"
              count={leaderboard ? leaderboard.length : undefined}
              unit={(leaderboard?.length ?? 0) === 1 ? "PLAYER" : "PLAYERS"}
              compact={isMobile}
              meta={
                isMobile && leaderboard && events ? (
                  <>
                    <span className="tabular-nums text-subtle">{leaderboard.length}</span>{" "}
                    {leaderboard.length === 1 ? "PLAYER" : "PLAYERS"},{" "}
                    <span className="tabular-nums text-subtle">{events.length}</span>{" "}
                    {events.length === 1 ? "EVENT" : "EVENTS"}
                  </>
                ) : undefined
              }
            />
            <LeaderboardTable
              rows={sortedLeaderboard}
              loading={leaderboard === undefined}
              variant={isMobile ? "mobile" : "desktop"}
              showScore={false}
              sort={sort}
              onSort={onSort}
              emptyMessage={`No player stats yet for ${activeSet}.`}
            />
          </section>

          <section className="order-1 lg:order-2 flex flex-col gap-4">
            {events === undefined ? (
              <EventsLoadingBlock />
            ) : upcoming.length === 0 && played.length === 0 ? (
              <div>
                <SectionHeading label="EVENTS" count={0} unit="EVENTS" />
                <EmptyHint>No pod drafts recorded yet for {activeSet}.</EmptyHint>
              </div>
            ) : isMobile ? (
              <MobileEventsBlock played={played} upcoming={upcoming} today={today} />
            ) : (
              <>
                {upcoming.length > 0 && (
                  <EventsBlock label="UPCOMING" events={upcoming} today={today} />
                )}
                {played.length > 0 && (
                  <EventsBlock label="PAST" events={played} today={today} defaultOpenFirst />
                )}
              </>
            )}
          </section>
        </div>
      </main>

      <Footer className="mt-auto px-5 py-4 md:pt-5 md:pb-3 shrink-0" />
    </div>
  );
}

function SectionHeading({
  label,
  count,
  unit,
  compact,
  meta,
}: {
  label: string;
  count?: number;
  unit: string;
  compact?: boolean;
  meta?: React.ReactNode;
}) {
  if (compact) {
    return (
      <div className="flex items-baseline justify-between gap-3 py-2 pl-4 pr-3 border-b border-border">
        <span className="font-display text-text text-[14px] tracking-[0.16em] leading-none">
          {label}
        </span>
        {meta && (
          <span className="font-display text-[10px] tracking-[0.14em] leading-none text-muted">
            {meta}
          </span>
        )}
      </div>
    );
  }
  return (
    <div className="flex items-baseline justify-between py-4 pl-2 pr-5 border-b border-border">
      <span
        className="font-display text-text tracking-[0.18em] leading-none"
        style={{ fontSize: 17 }}
      >
        {label}
      </span>
      {count === undefined ? (
        <span className="inline-block h-3.5 w-24 bg-surface2 animate-pulse" />
      ) : (
        <span
          className="font-display tracking-[0.18em] leading-none flex items-baseline gap-1.5"
          style={{ fontSize: 17 }}
        >
          <span className="tabular-nums text-subtle">{count}</span>
          <span className="text-muted">{unit}</span>
        </span>
      )}
    </div>
  );
}

function EventsBlock({
  label,
  events,
  today,
  defaultOpenFirst = false,
}: {
  label: string;
  events: PodEventSummary[];
  today: string;
  defaultOpenFirst?: boolean;
}) {
  return (
    <div>
      <SectionHeading
        label={label}
        count={events.length}
        unit={events.length === 1 ? "EVENT" : "EVENTS"}
      />
      <div className="flex flex-col lg:gap-2">
        {events.map((e, i) => (
          <EventRow
            key={e.eventId}
            event={e}
            index={i}
            today={today}
            defaultOpen={defaultOpenFirst && i === 0}
          />
        ))}
      </div>
    </div>
  );
}

function EventRow({
  event,
  index,
  today,
  defaultOpen = false,
}: {
  event: PodEventSummary;
  index: number;
  today: string;
  defaultOpen?: boolean;
}) {
  const isUpcoming = !event.championDisplayName && event.eventDate > today;
  const expandable = !isUpcoming;
  const isJoinable = isUpcoming && !!event.discordEventId;
  const [open, setOpen] = useState(defaultOpen && expandable);
  const headerClass = cn(
    "group w-full min-h-[68px] flex items-stretch text-left bg-transparent border-0 no-underline transition-colors",
    expandable || isJoinable ? "cursor-pointer" : "cursor-default",
    open
      ? "bg-surface2/40"
      : expandable
      ? "hover:bg-surface2/30"
      : isJoinable
      ? "hover:bg-green/15"
      : "",
  );
  const headerContent = (
    <>
      <DateRail
        date={event.eventDate}
        highlighted={open}
        time={isUpcoming ? formatLocalTime(event.eventTime) : null}
      />
      <EventRowBody event={event} today={today} />
      {isJoinable ? (
        <JoinEventCTA />
      ) : (
        <EventRowMeta open={open} expandable={expandable} />
      )}
    </>
  );
  return (
    <div
      className="bg-surface border-b lg:border border-border first:lg:border-t-0 transition-colors animate-fadeUpIn"
      style={{ animationDelay: `${Math.min(index, 6) * 45}ms` }}
    >
      {isJoinable ? (
        <a
          href={`https://discord.com/events/${DISCORD_GUILD_ID}/${event.discordEventId}`}
          target="_blank"
          rel="noreferrer"
          className={headerClass}
        >
          {headerContent}
        </a>
      ) : expandable ? (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className={headerClass}
        >
          {headerContent}
        </button>
      ) : (
        <div className={headerClass}>{headerContent}</div>
      )}

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-200 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
        aria-hidden={!open}
      >
        <div className="overflow-hidden">{open && <EventStandings event={event} />}</div>
      </div>
    </div>
  );
}

function JoinEventCTA() {
  return (
    <div className="flex items-center pr-3 md:pr-4 pl-2 shrink-0 self-center">
      <span
        className="bg-green text-bg group-hover:bg-green-2 transition-colors inline-flex items-center gap-3 py-2 pl-3.5 pr-5 border-none"
        style={{ clipPath: "polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%)" }}
      >
        <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-bg text-text shrink-0">
          <DiscordIcon size={15} />
        </span>
        <span className="font-display text-[13px] tracking-[0.14em] leading-none">
          JOIN EVENT
        </span>
        <ArrowRight size={14} strokeWidth={3} className="shrink-0" />
      </span>
    </div>
  );
}

function DateRail({
  date,
  highlighted,
  time = null,
}: {
  date: string;
  highlighted: boolean;
  time?: string | null;
}) {
  const { month, day } = parseMonthDay(date);
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center border-r transition-colors",
        time ? "px-1.5 min-w-[84px] md:min-w-[88px]" : "px-3 min-w-[72px] md:min-w-[78px]",
        highlighted
          ? "bg-surface2 border-border2"
          : "bg-surface2/40 border-border group-hover:bg-surface2/70",
      )}
    >
      {time ? (
        <>
          <div className="flex items-baseline gap-2">
            <span
              className="font-display text-muted leading-none tracking-[0.04em]"
              style={{ fontSize: 18 }}
            >
              {month}
            </span>
            <span
              className="font-display text-text leading-none tabular-nums"
              style={{ fontSize: 22 }}
            >
              {String(day).padStart(2, "0")}
            </span>
          </div>
          <span
            className="font-display text-text leading-none tabular-nums tracking-[0.04em] mt-1"
            style={{ fontSize: 18 }}
          >
            {time}
          </span>
        </>
      ) : (
        <>
          <span
            className="font-display text-muted leading-none tracking-[0.04em]"
            style={{ fontSize: 20 }}
          >
            {month}
          </span>
          <span
            className="font-display text-text leading-none tabular-nums mt-0.5"
            style={{ fontSize: 22 }}
          >
            {String(day).padStart(2, "0")}
          </span>
        </>
      )}
    </div>
  );
}

function EventRowBody({ event, today }: { event: PodEventSummary; today: string }) {
  const hasChamp = !!event.championDisplayName;
  const inProgress = !hasChamp && event.eventDate <= today;
  const isUpcoming = !hasChamp && event.eventDate > today;
  return (
    <div
      className={cn(
        "flex-1 min-w-0 py-2.5 px-3 md:px-4",
        isUpcoming
          ? "flex flex-col items-start gap-1.5 lg:flex-row lg:items-center lg:gap-4"
          : "flex items-center gap-4",
      )}
    >
      <span
        className={cn(
          "font-display text-text min-w-0 line-clamp-2 lg:line-clamp-none lg:truncate",
          isUpcoming ? "lg:flex-none" : "flex-1 lg:flex-none lg:w-2/5",
        )}
        style={{ fontSize: 21, letterSpacing: "0.04em", lineHeight: 1.15 }}
      >
        {cleanPodEventName(event.name, event.setCode).toUpperCase()}
      </span>
      {isUpcoming && <CountdownChip iso={event.eventTime} />}
      {hasChamp && event.championDisplayName && (
        <div className="flex flex-col items-center gap-1 min-w-0 max-w-[50%] lg:flex-row lg:items-center lg:gap-2.5 lg:max-w-none lg:shrink-0 lg:w-[260px]">
          <div className="flex items-center gap-1 min-w-0 max-w-full lg:contents">
            <Trophy size={17} color="#ffc63a" className="-translate-y-[1px]" />
            <span
              className="font-display text-text tracking-[0.04em] truncate max-w-full"
              style={{ fontSize: 18, lineHeight: 1 }}
            >
              {stripDiscriminator(event.championDisplayName).toUpperCase()}
            </span>
          </div>
          {event.championDeckColors && (
            <Pips colors={event.championDeckColors} size={15} />
          )}
        </div>
      )}
      {inProgress && (
        <span
          className="font-display text-muted tracking-[0.18em] shrink-0"
          style={{ fontSize: 10 }}
        >
          IN PROGRESS
        </span>
      )}
      <div className="hidden lg:block flex-1" />
    </div>
  );
}

function EventRowMeta({ open, expandable }: { open: boolean; expandable: boolean }) {
  return (
    <div className="flex items-center pr-3 md:pr-4 pl-2 shrink-0 self-center">
      {expandable && (
        <ChevronDown
          size={16}
          className={cn(
            "text-muted transition-all duration-200 group-hover:text-text",
            open && "rotate-180 text-text",
          )}
        />
      )}
    </div>
  );
}

const STANDING_COLS_CLASS =
  "[grid-template-columns:28px_1fr_60px_50px_38px] " +
  "lg:[grid-template-columns:44px_1fr_80px_70px_150px]";

function EventStandings({ event }: { event: PodEventSummary }) {
  const { data: rows, isLoading } = usePodEventParticipants(event.eventId);
  const [deckTarget, setDeckTarget] = useState<PodEventParticipantRow | null>(null);
  const sorted = useMemo(() => {
    if (!rows) return [];
    return [...rows].sort((a, b) => (a.placement ?? 99) - (b.placement ?? 99));
  }, [rows]);
  return (
    <>
      <div className="border-t border-dashed border-border2">
        <div className="flex flex-col gap-[1px] pb-[1px] bg-bg">
          {isLoading
            ? Array.from({ length: 8 }).map((_, i) => <StandingRowSkeleton key={i} />)
            : sorted.map((p) => (
                <StandingRow
                  key={`${p.eventId}-${p.displayName}`}
                  p={p}
                  onClick={p.deckScreenshotUrl ? () => setDeckTarget(p) : undefined}
                />
              ))}
        </div>
        <Link to={`/pods/${event.slug}`} className="block no-underline">
          <div className="flex justify-end items-center gap-4 px-3 md:px-4 py-3 bg-surface hover:bg-green/5 transition-colors cursor-pointer">
            <span className="text-muted text-[13px] font-body">
              {BREAKDOWN_CAPTION}
            </span>
            <ChamferedButton>
              <span className="inline-flex items-center gap-2">
                VIEW BREAKDOWN
                <ArrowRight size={12} />
              </span>
            </ChamferedButton>
          </div>
        </Link>
      </div>
      {deckTarget && (
        <DeckScreenshotModal
          participant={{
            eventId: deckTarget.eventId,
            displayName: podDiscordName(deckTarget),
            participantDisplayName: deckTarget.displayName,
            deckColors: deckTarget.deckColors,
            deckScreenshotUrl: deckTarget.deckScreenshotUrl,
            deckScreenshotCaption: deckTarget.deckScreenshotCaption,
            record: deckTarget.record,
          }}
          breakdownHref={`/pods/${event.slug}?player=${encodeURIComponent(podDiscordName(deckTarget))}`}
          onClose={() => setDeckTarget(null)}
        />
      )}
    </>
  );
}

function StandingRow({
  p,
  onClick,
}: {
  p: PodEventParticipantRow;
  onClick?: () => void;
}) {
  const wins = p.record ? Number(p.record.split("-")[0] || 0) : 0;
  const losses = p.record ? Number(p.record.split("-")[1] || 0) : 0;
  const name = podDiscordName(p);
  const interactive = !!onClick;
  return (
    <div
      onClick={onClick}
      className={cn(
        "group/row grid items-center gap-x-2 lg:gap-x-3 py-2.5 pl-2 pr-3 lg:pr-5 bg-surface transition-colors",
        STANDING_COLS_CLASS,
        interactive && "cursor-pointer hover:bg-surface2",
      )}
    >
      <span className="mono text-[13px] text-muted text-center">{p.placement ?? ""}</span>
      <div className="flex items-center gap-2 lg:gap-2.5 min-w-0">
        <AAvatar displayName={name} avatarUrl={p.avatarUrl} size={28} />
        <span
          className="font-display text-text leading-none tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis"
          style={{ fontSize: 16 }}
        >
          {name.toUpperCase()}
        </span>
      </div>
      <div className="flex items-center">
        {p.deckColors ? (
          <Pips colors={p.deckColors} size={14} />
        ) : (
          <span className="text-dim text-[12px]">—</span>
        )}
      </div>
      <Record className="mono text-center text-[13px]" wins={wins} losses={losses} />
      {interactive ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onClick?.();
          }}
          className="group/deck inline-flex items-center justify-center gap-2 bg-bg border border-border hover:border-green/60 hover:bg-green/10 group-hover/row:border-green/60 group-hover/row:bg-green/10 transition-colors px-1.5 lg:px-3 cursor-pointer whitespace-nowrap"
          style={{ height: 34 }}
        >
          <span
            className="hidden lg:inline font-display tracking-[0.16em] text-text group-hover/deck:text-green group-hover/row:text-green transition-colors leading-none"
            style={{ fontSize: 14 }}
          >
            VIEW DECK
          </span>
          <TbCards
            size={17}
            aria-hidden="true"
            className="text-text group-hover/deck:text-green group-hover/row:text-green transition-colors"
          />
        </button>
      ) : (
        <span />
      )}
    </div>
  );
}

function StandingRowSkeleton() {
  return (
    <div
      className={cn(
        "grid items-center gap-x-2 lg:gap-x-3 py-2.5 pl-2 pr-3 lg:pr-5 bg-surface",
        STANDING_COLS_CLASS,
      )}
    >
      <div className="h-3 w-3 bg-surface2 animate-pulse mx-auto" />
      <div className="flex items-center gap-2.5">
        <div className="w-7 h-7 bg-surface2" />
        <div className="h-3.5 w-32 bg-surface2 animate-pulse" />
      </div>
      <div className="h-3.5 w-14 bg-surface2 animate-pulse" />
      <div className="h-3.5 w-10 bg-surface2 animate-pulse ml-auto" />
      <div className="h-[34px] w-full bg-surface2 animate-pulse" />
    </div>
  );
}

function EventRowSkeleton({ index }: { index: number }) {
  return (
    <div
      className="bg-surface border-b lg:border border-border first:lg:border-t-0 min-h-[68px] flex items-stretch animate-fadeUpIn"
      style={{ animationDelay: `${Math.min(index, 6) * 45}ms` }}
    >
      <div className="px-3 min-w-[72px] md:min-w-[78px] bg-surface2/40 border-r border-border flex flex-col items-center justify-center gap-1.5">
        <div className="h-4 w-10 bg-surface2 animate-pulse" />
        <div className="h-5 w-8 bg-surface2 animate-pulse" />
      </div>
      <div className="flex-1 flex items-center px-3 md:px-4">
        <div className="h-4 w-2/3 bg-surface2 animate-pulse" />
      </div>
    </div>
  );
}

function EventsLoadingBlock() {
  return (
    <div>
      <SectionHeading label="EVENTS" unit="EVENTS" />
      <div className="flex flex-col lg:gap-2">
        {[0, 1, 2].map((i) => (
          <EventRowSkeleton key={i} index={i} />
        ))}
      </div>
    </div>
  );
}

type EventsTab = "last" | "upcoming" | "all";

function MobileEventsBlock({
  played,
  upcoming,
  today,
}: {
  played: PodEventSummary[];
  upcoming: PodEventSummary[];
  today: string;
}) {
  const [tab, setTab] = useState<EventsTab>("last");
  const list = useMemo<PodEventSummary[]>(() => {
    if (tab === "last") return played[0] ? [played[0]] : [];
    if (tab === "upcoming") return upcoming;
    return played.slice(1);
  }, [tab, played, upcoming]);
  return (
    <div>
      <div className="flex border-b border-border">
        <EventsTabButton active={tab === "last"} onClick={() => setTab("last")}>
          LAST EVENT
        </EventsTabButton>
        <EventsTabButton active={tab === "upcoming"} onClick={() => setTab("upcoming")}>
          UPCOMING
        </EventsTabButton>
        <EventsTabButton active={tab === "all"} onClick={() => setTab("all")}>
          ALL
        </EventsTabButton>
      </div>
      {list.length === 0 ? (
        <EmptyHint>
          {tab === "upcoming" ? "No upcoming pod drafts." : "No pod drafts yet."}
        </EmptyHint>
      ) : (
        <div className="flex flex-col">
          {list.map((e, i) => (
            <EventRow
              key={e.eventId}
              event={e}
              index={i}
              today={today}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function EventsTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex-1 py-2.5 px-1.5 bg-transparent cursor-pointer font-display text-[11px] tracking-[0.16em] transition-colors border-b-2 border-solid",
        active ? "text-text border-green" : "text-muted border-transparent",
      )}
      style={active ? { marginBottom: -1 } : undefined}
    >
      {children}
    </button>
  );
}

function EmptyHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-muted text-[13px] py-4 px-2 bg-surface border border-border">
      {children}
    </div>
  );
}

function MobileSetStrip({
  activeSet,
  availableSets,
  onSelectSet,
}: {
  activeSet: string;
  availableSets: SetSummary[];
  onSelectSet: (code: string) => void;
}) {
  return (
    <div className="px-3 pt-2 pb-1 border-b border-border bg-surface flex items-center gap-3">
      <div className="pl-1 pr-1">
        <SetGlyph code={activeSet} size={32} />
      </div>
      <span className="font-display text-text tracking-[0.04em]" style={{ fontSize: 28, lineHeight: 1 }}>
        {activeSet}
      </span>
      {availableSets.length > 0 && (
        <div className="ml-auto basis-[34%] min-w-0">
          <SetSwitcherMobile sets={availableSets} activeCode={activeSet} onChange={onSelectSet} />
        </div>
      )}
    </div>
  );
}

function SetHero({
  activeSet,
  setMeta,
  sets,
  onSelectSet,
}: {
  activeSet: string;
  setMeta: SetSummary | undefined;
  sets: SetSummary[];
  onSelectSet: (code: string) => void;
}) {
  const week = weekOfSet(setMeta);
  const isActive = setMeta?.isActive ?? false;
  return (
    <div className="relative px-10 py-5 border-b border-border bg-surface flex items-center gap-6">
      <SetGlyph code={activeSet} size={84} />
      <div>
        <SectionLabel size={13} className={isActive ? "" : "invisible"}>CURRENT SET</SectionLabel>
        <div className="flex items-baseline gap-3.5 mt-0.5">
          <span className="font-display tracking-[0.04em]" style={{ fontSize: 56, lineHeight: 0.9 }}>
            {activeSet}
          </span>
          <span className="font-display text-[22px] text-muted tracking-[0.06em]">
            {setMeta?.name?.toUpperCase() ?? ""}
          </span>
        </div>
        <div className="mono text-[11px] text-muted mt-1">
          {setMeta && fmtRange(setMeta.startDate, setMeta.endDate)}
          {week && ` · ${week}`}
        </div>
      </div>
      <div className="flex-1" />
      {sets.length > 0 && (
        <SetSwitcherDesktop sets={sets} activeCode={activeSet} onChange={onSelectSet} />
      )}
    </div>
  );
}
