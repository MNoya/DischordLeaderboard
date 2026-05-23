import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { AAvatar, ALogo, SetGlyph, Trophy, fmtPts } from "../components/Brand";
import {
  ArrowUp,
  BsAsterisk,
  BsPaletteFill,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Info,
} from "../components/Icons";
import { Pip, Pips } from "../components/ManaPips";
import { StatChip } from "../components/StatChip";
import { PointsBreakdown } from "../components/PointsBreakdown";
import { FilterDropdown } from "../components/FilterDropdown";
import { SectionLabel } from "../components/SectionLabel";
import { Record } from "../components/Record";
import { DonutChart } from "../components/DonutChart";
import { ErrorState } from "../components/ErrorState";
import { TrophyCount } from "../components/TrophyCount";
import { SetCodeDropdown } from "../components/SetCodeDropdown";
import { MobilePageHeader } from "../components/PageNav";
import { RankBadge } from "../components/RankBadge";

import { useAvailableFormats, useColorChips, useDraftEvents, useLeaderboard, usePlayerProfile, useSets } from "../data/hooks";
import { computeScore, type ScoringStatRow } from "../data/scoring";
import { colorsOf, effectiveColorCount, eventDate, fmtShortDate, formatTag, isFlashbackEvent, mainColors, prettyFormat, winPct } from "../data/utils";
import {
  colorsDisplayName,
  deckColorParts,
  formatDeckColors,
  FORMAT_LABEL_GROUPS,
  FORMAT_OPTIONS,
  matchesFormatFilter,
  MULTI,
  OTHER,
  type FilterOption,
} from "../data/filters";
import { FMT_COLORS, renderFormatOption, shortFormat } from "../data/format-display";
import { cn } from "../lib/utils";
import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerProfile,
  SetSummary,
} from "../types/leaderboard";

// ─── Color palettes ────────────────────────────────────────────────────────

const COLOR_STROKES: Record<string, string> = {
  W: "#f0f2c0",
  U: "#b5cde3",
  B: "#aca29a",
  R: "#db8664",
  G: "#93b483",
};

const COLOR_KEYS: Array<"W" | "U" | "B" | "R" | "G"> = ["W", "U", "B", "R", "G"];

const COLOR_NAMES: Record<"W" | "U" | "B" | "R" | "G", string> = {
  W: "White",
  U: "Blue",
  B: "Black",
  R: "Red",
  G: "Green",
};

function comboColors(combo: string): string[] {
  const out: string[] = [];
  for (const c of combo) {
    const hex = COLOR_STROKES[c];
    if (hex) out.push(hex);
  }
  return out.length > 0 ? out : ["#7a8395"];
}

const renderColorOption = (opt: FilterOption) => {
  if (opt.value === "ALL") return <span>{opt.label}</span>;
  if (opt.value === MULTI) {
    return (
      <span className="flex items-center gap-2">
        <BsPaletteFill size={12} aria-hidden="true" />
        <span>{opt.label}</span>
      </span>
    );
  }
  if (opt.value === OTHER) {
    return (
      <span className="flex items-center gap-2">
        <BsAsterisk size={11} aria-hidden="true" />
        <span>{opt.label}</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <Pips colors={opt.value} size={12} />
      <span>{opt.label}</span>
    </span>
  );
};

// ─── Page entry ────────────────────────────────────────────────────────────

export function PlayerPage() {
  const params = useParams<{ slug: string; setCode?: string }>();
  const slug = params.slug!;
  const navigate = useNavigate();
  const { data: sets } = useSets();
  const setCode = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const { data: profile, isLoading, isFetching, error } = usePlayerProfile(slug, setCode);
  const { data: events, isFetching: isFetchingEvents } = useDraftEvents(slug, setCode);
  const showLoadingBar = (isFetching || isFetchingEvents) && !isLoading;
  // Sibling navigation needs the leaderboard rows so we know who's adjacent
  // by rank. Cached behind TanStack Query — same fetch as the leaderboard
  // page, so navigating between profiles doesn't re-hit the network.
  const { data: leaderboardRows } = useLeaderboard(setCode);
  const isMobile = useIsMobile();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug, setCode]);

  const liveSetCode = sets?.find((s) => s.isActive)?.code;
  const [topSearchParams] = useSearchParams();
  useEffect(() => {
    if (params.setCode && liveSetCode && params.setCode === liveSetCode) {
      navigate(
        { pathname: `/player/${slug}`, search: topSearchParams.toString() },
        { replace: true },
      );
    }
  }, [params.setCode, liveSetCode, slug, navigate, topSearchParams]);

  const idx = leaderboardRows?.findIndex((r) => r.slug === slug) ?? -1;
  const prevSlug = idx > 0 ? leaderboardRows![idx - 1].slug : null;
  const nextSlug = idx >= 0 && leaderboardRows && idx < leaderboardRows.length - 1
    ? leaderboardRows[idx + 1].slug
    : null;
  const sibling: SiblingNav = { setCode, prevSlug, nextSlug };

  const topQs = topSearchParams.toString();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      const t = e.target;
      if (t instanceof HTMLElement) {
        if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return;
      }
      if (e.key === "ArrowLeft" && prevSlug) {
        e.preventDefault();
        navigate({ pathname: `/${setCode}/player/${prevSlug}`, search: topQs });
      } else if (e.key === "ArrowRight" && nextSlug) {
        e.preventDefault();
        navigate({ pathname: `/${setCode}/player/${nextSlug}`, search: topQs });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [prevSlug, nextSlug, setCode, navigate, topQs]);

  if (error) {
    return (
      <div className="bg-bg text-text min-h-screen animate-fadeIn">
        {isMobile ? (
          <MobilePlayerHeader sibling={sibling} navigate={navigate} qs={topQs} />
        ) : (
          <AppHeader subtitle="PLAYER PROFILE" />
        )}
        <ErrorState error={error as Error} compact={isMobile} />
      </div>
    );
  }

  if (isLoading || !profile) {
    return (
      <div className="bg-bg text-text min-h-screen animate-fadeIn">
        {isMobile ? (
          <MobilePlayerHeader sibling={sibling} navigate={navigate} qs={topQs} />
        ) : (
          <AppHeader subtitle="PLAYER PROFILE" />
        )}
        {isLoading ? (
          isMobile ? <MobileSkeleton /> : <DesktopSkeleton />
        ) : (
          <div className="p-20 text-center text-muted font-display tracking-[0.2em]">
            PLAYER NOT FOUND
          </div>
        )}
      </div>
    );
  }

  const onChangeSet = (newCode: string) => {
    navigate({ pathname: `/${newCode}/player/${slug}`, search: topQs });
  };

  return (
    <>
      {showLoadingBar && <TopLoadingBar />}
      {isMobile ? (
        <Mobile profile={profile} events={events ?? []} sibling={sibling} sets={sets} onChangeSet={onChangeSet} />
      ) : (
        <Desktop profile={profile} events={events ?? []} sibling={sibling} sets={sets} onChangeSet={onChangeSet} />
      )}
    </>
  );
}

function TopLoadingBar() {
  return (
    <div
      aria-hidden="true"
      className="fixed top-0 left-0 right-0 h-[2px] z-[60] overflow-hidden pointer-events-none bg-border/30"
    >
      <div className="h-full w-1/3 bg-green animate-loadingBar" />
    </div>
  );
}

function useUrlFilters(): [
  string,
  (v: string) => void,
  string,
  (v: string) => void,
  string,
] {
  const [searchParams, setSearchParams] = useSearchParams();
  const formatFilter = searchParams.get("format") ?? "ALL";
  const colorsFilter = searchParams.get("colors") ?? "ALL";
  const update = (key: "format" | "colors", value: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value === "ALL") next.delete(key);
      else next.set(key, value);
      return next;
    }, { replace: true });
  };
  return [
    formatFilter,
    (v) => update("format", v),
    colorsFilter,
    (v) => update("colors", v),
    searchParams.toString(),
  ];
}

function MobilePlayerHeader({
  sibling,
  navigate,
  qs = "",
}: {
  sibling: SiblingNav;
  navigate: ReturnType<typeof useNavigate>;
  qs?: string;
}) {
  const toFor = (s: string | null) =>
    s ? { pathname: `/${sibling.setCode}/player/${s}`, search: qs } : null;
  return (
    <MobilePageHeader
      backOnClick={() => navigate({ pathname: `/${sibling.setCode}`, search: qs })}
      prevTo={toFor(sibling.prevSlug)}
      nextTo={toFor(sibling.nextSlug)}
      prevAriaLabel="Previous player"
      nextAriaLabel="Next player"
    />
  );
}

function SkeletonBox({ className }: { className?: string }) {
  return <div className={cn("bg-surface2 animate-pulse", className)} />;
}

function MobileSkeleton() {
  return (
    <>
      <section
        className="px-[18px] pt-5 pb-8 border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center gap-4">
          <SkeletonBox className="w-[84px] h-[84px] rounded-full" />
          <div className="flex-1 min-w-0 flex flex-col gap-2">
            <SkeletonBox className="w-44 h-8" />
            <SkeletonBox className="w-24 h-3" />
          </div>
        </div>
        <div className="mt-[18px] grid grid-cols-5 gap-[5px]">
          {[0, 1, 2, 3, 4].map((i) => (
            <SkeletonBox key={i} className="h-12" />
          ))}
        </div>
      </section>

      <section className="border-b border-border">
        <div className="flex border-b border-border">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex-1 py-2.5 px-1.5 flex justify-center">
              <SkeletonBox className="w-3/4 h-3" />
            </div>
          ))}
        </div>
        <div className="px-[18px] py-4 flex items-center gap-3.5">
          <SkeletonBox className="w-[108px] h-[108px] rounded-full" />
          <div className="flex-1 flex flex-col gap-1.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <SkeletonBox key={i} className="h-5" />
            ))}
          </div>
        </div>
      </section>

      <section className="py-4 px-[18px]">
        <SkeletonBox className="w-32 h-3 mb-3" />
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="grid gap-2.5 py-2.5 border-b border-border items-center"
            style={{ gridTemplateColumns: "20px 1fr auto" }}
          >
            <SkeletonBox className="w-4 h-4" />
            <div className="flex flex-col gap-1.5">
              <SkeletonBox className="w-28 h-3" />
              <SkeletonBox className="w-20 h-2" />
            </div>
            <SkeletonBox className="w-10 h-3.5" />
          </div>
        ))}
      </section>
    </>
  );
}

function DesktopSkeleton() {
  return (
    <>
      <section
        className="px-10 pt-7 pb-[30px] border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center justify-between mb-3.5">
          <SkeletonBox className="w-44 h-3" />
          <SkeletonBox className="w-32 h-3" />
        </div>
        <div className="flex items-center gap-7">
          <SkeletonBox className="w-[120px] h-[120px] rounded-full" />
          <div className="flex-1 min-w-0 flex flex-col gap-3">
            <SkeletonBox className="w-72 h-12" />
            <SkeletonBox className="w-40 h-4" />
          </div>
          <div
            className="grid border border-border2 self-stretch"
            style={{ flex: "0 0 720px", gridTemplateColumns: "1fr 1fr 1.3fr 1fr 0.9fr" }}
          >
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className={cn(
                  "py-3.5 px-3 flex flex-col items-center gap-3",
                  i < 4 && "border-r border-border2",
                )}
              >
                <SkeletonBox className="w-12 h-2.5" />
                <SkeletonBox className="w-16 h-10" />
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="grid" style={{ gridTemplateColumns: "440px 1fr" }}>
        <section className="py-6 pl-10 pr-8 border-r border-border flex flex-col gap-6">
          {[0, 1, 2].map((s) => (
            <div key={s}>
              <div className="flex justify-center mb-3.5" style={{ width: 148 }}>
                <SkeletonBox className="w-24 h-3" />
              </div>
              <div className="flex items-center gap-5">
                <SkeletonBox className="w-[148px] h-[148px] rounded-full shrink-0" />
                <div className="flex-1 flex flex-col gap-2">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <SkeletonBox key={i} className="h-5" />
                  ))}
                </div>
              </div>
            </div>
          ))}
        </section>

        <section className="py-6 px-10">
          <div className="flex justify-between items-center mb-3">
            <SkeletonBox className="w-40 h-3" />
            <div className="flex gap-2">
              <SkeletonBox className="w-44 h-8" />
              <SkeletonBox className="w-44 h-8" />
            </div>
          </div>
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div
              key={i}
              className="grid gap-3 py-[6px] border-b border-border items-center"
              style={{ gridTemplateColumns: "30px 110px 170px 1fr 90px" }}
            >
              <SkeletonBox className="w-4 h-4 mx-auto" />
              <SkeletonBox className="w-20 h-3" />
              <SkeletonBox className="w-16 h-3.5" />
              <SkeletonBox className="w-32 h-3" />
              <SkeletonBox className="w-12 h-5" />
            </div>
          ))}
        </section>
      </div>
    </>
  );
}

interface SiblingNav {
  setCode: string;
  prevSlug: string | null;
  nextSlug: string | null;
}

// ─── Aggregation ───────────────────────────────────────────────────────────

interface PlayerAggregates {
  colorCount: Record<"W" | "U" | "B" | "R" | "G", number>;
  comboCount: Record<string, number>;
  comboTrophies: Record<string, number>;
}

interface StatStripStats {
  trophies: number;
  events: number;
  wins: number;
  losses: number;
  score: number;
}

function statsFromEvents(events: PlayerDraftEvent[]): StatStripStats {
  let trophies = 0;
  let wins = 0;
  let losses = 0;
  let countedEvents = 0;
  const rows: ScoringStatRow[] = [];
  for (const e of events) {
    if (e.format.startsWith("MidWeek")) continue;
    if (e.isTrophy) trophies += 1;
    wins += e.wins;
    losses += e.losses;
    countedEvents += 1;
    rows.push({ format: e.format, wins: e.wins, losses: e.losses, trophies: e.isTrophy ? 1 : 0, events: 1 });
  }
  return { trophies, events: countedEvents, wins, losses, score: computeScore(rows) };
}

function aggregate(events: PlayerDraftEvent[]): PlayerAggregates {
  const colorCount: PlayerAggregates["colorCount"] = { W: 0, U: 0, B: 0, R: 0, G: 0 };
  const comboCount: Record<string, number> = {};
  const comboTrophies: Record<string, number> = {};
  for (const e of events) {
    const main = mainColors(e.colors);
    for (const c of main) {
      if (c in colorCount) colorCount[c as keyof typeof colorCount]++;
    }
    const combo = colorsOf(e.colors);
    if (combo.length === 0) continue;
    comboCount[combo] = (comboCount[combo] ?? 0) + 1;
    if (e.isTrophy) comboTrophies[combo] = (comboTrophies[combo] ?? 0) + 1;
  }
  return { colorCount, comboCount, comboTrophies };
}

// ─── Desktop ───────────────────────────────────────────────────────────────

function Desktop({
  profile,
  events,
  sibling,
  sets,
  onChangeSet,
}: {
  profile: PlayerProfile;
  events: PlayerDraftEvent[];
  sibling: SiblingNav;
  sets: SetSummary[] | undefined;
  onChangeSet: (code: string) => void;
}) {
  const navigate = useNavigate();

  const [formatFilter, setFormatFilter, colorsFilter, setColorsFilter, qs] =
    useUrlFilters();

  const { chips: colorChips, otherCombos } = useColorChips(profile.setCode);
  const colorOptions = useMemo<FilterOption[]>(() => {
    const opts: FilterOption[] = [{ value: "ALL", label: "ALL COLORS" }];
    for (const c of colorChips) {
      if (c === MULTI) opts.push({ value: MULTI, label: "SOUP" });
      else if (c === OTHER) opts.push({ value: OTHER, label: "OTHER" });
      else opts.push({ value: c, label: colorsDisplayName(c) });
    }
    return opts;
  }, [colorChips]);
  const { data: availableFormatLabels } = useAvailableFormats(profile.setCode);
  const formatOptions = useMemo(() => {
    if (!availableFormatLabels) return FORMAT_OPTIONS;
    const available = new Set(availableFormatLabels);
    return FORMAT_OPTIONS.filter((opt) => {
      if (opt.value === "ALL") return true;
      const labels = FORMAT_LABEL_GROUPS[opt.value] ?? [opt.value];
      return labels.some((l) => available.has(l));
    });
  }, [availableFormatLabels]);
  const otherSet = useMemo(() => new Set(otherCombos), [otherCombos]);

  const filtered = useMemo(
    () =>
      events.filter((e) => {
        if (formatFilter !== "ALL" && !matchesFormatFilter(e.format, formatFilter)) return false;
        if (colorsFilter !== "ALL") {
          if (colorsFilter === MULTI) {
            if (effectiveColorCount(e.colors) < 4) return false;
          } else if (colorsFilter === OTHER) {
            if (effectiveColorCount(e.colors) >= 4) return false;
            if (!otherSet.has(colorsOf(e.colors))) return false;
          } else if (colorsOf(e.colors) !== colorsFilter) return false;
        }
        return true;
      }),
    [events, formatFilter, colorsFilter, otherSet]
  );

  const filtersActive = formatFilter !== "ALL" || colorsFilter !== "ALL";
  const stats: StatStripStats = useMemo(
    () =>
      filtersActive
        ? statsFromEvents(filtered)
        : { trophies: profile.trophies, events: profile.events, wins: profile.wins, losses: profile.losses, score: profile.score },
    [filtersActive, filtered, profile.trophies, profile.events, profile.wins, profile.losses, profile.score],
  );
  const wp = winPct(stats.wins, stats.losses);
  const [pointsModalOpen, setPointsModalOpen] = useState(false);
  const pointsBtnRef = useRef<HTMLButtonElement>(null);

  return (
    <div className="bg-bg text-text min-h-screen animate-fadeIn">
      <AppHeader subtitle="PLAYER PROFILE" />

      <section
        className="px-10 pt-5 pb-[30px] border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <BackButton onClick={() => navigate({ pathname: `/${profile.setCode}`, search: qs })} inline />
          <SiblingNavButtons sibling={sibling} qs={qs} />
        </div>
        <div className="flex items-end gap-7">
          <AAvatar displayName={profile.displayName} avatarUrl={profile.avatarUrl} size={120} green />
          <div className="shrink-0">
            <h1
              className="font-display tracking-[0.03em] m-0 whitespace-nowrap pl-[5px]"
              style={{ fontSize: 64, lineHeight: 0.95 }}
            >
              {profile.displayName.toUpperCase()}
            </h1>
            <div className="mt-2 flex items-center gap-3 font-display tracking-[0.18em]">
              {sets ? (
                <SetCodeDropdown sets={sets} activeCode={profile.setCode} onChange={onChangeSet} />
              ) : (
                <span className="text-[22px]">{profile.setCode}</span>
              )}
              <RankBadge rank={profile.rank} size="lg" />
            </div>
          </div>
          <StatStrip
            stats={stats}
            wp={wp}
            onPointsClick={() => setPointsModalOpen((o) => !o)}
            pointsBtnRef={pointsBtnRef}
          />
        </div>
      </section>

      <div className="grid" style={{ gridTemplateColumns: "440px 1fr" }}>
        <BreakdownPanel profile={profile} events={events} />
        <DraftLogDesktop
          events={events}
          filtered={filtered}
          formatFilter={formatFilter}
          setFormatFilter={setFormatFilter}
          colorsFilter={colorsFilter}
          setColorsFilter={setColorsFilter}
          colorOptions={colorOptions}
          formatOptions={formatOptions}
          setEndDate={sets?.find((s) => s.code === profile.setCode)?.endDate ?? null}
        />
      </div>

      <PointsBreakdown
        open={pointsModalOpen}
        onClose={() => setPointsModalOpen(false)}
        breakdown={profile.formatBreakdown}
        anchorRef={pointsBtnRef}
      />
    </div>
  );
}

function StatStrip({
  stats,
  wp,
  onPointsClick,
  pointsBtnRef,
}: {
  stats: StatStripStats;
  wp: string;
  onPointsClick?: () => void;
  pointsBtnRef?: React.RefObject<HTMLButtonElement>;
}) {
  const valueCls = "font-display leading-none text-[clamp(26px,3vw,44px)]";
  const tiles: Array<{
    label: string;
    value: React.ReactNode;
    accent?: boolean;
    onClick?: () => void;
    btnRef?: React.RefObject<HTMLButtonElement>;
  }> = [
    {
      label: "TROPHIES",
      value: (
        <span className="flex items-center gap-1.5">
          <Trophy size={26} color="#ffc63a" />
          <span className={valueCls}>{stats.trophies}</span>
        </span>
      ),
    },
    {
      label: "EVENTS",
      value: <span className={valueCls}>{stats.events}</span>,
    },
    {
      label: "RECORD",
      value: (
        <Record
          mono
          wins={stats.wins}
          losses={stats.losses}
          separatorMargin={4}
          className={valueCls}
        />
      ),
    },
    {
      label: "WIN %",
      value: (
        <span className={valueCls}>
          {wp}
          <span className="text-[clamp(14px,1.5vw,22px)] text-muted">%</span>
        </span>
      ),
    },
    {
      label: "POINTS",
      value: <span className={cn(valueCls, "text-green")}>{fmtPts(stats.score)}</span>,
      accent: true,
      onClick: onPointsClick,
      btnRef: pointsBtnRef,
    },
  ];
  return (
    <div
      className="grid border border-border2 bg-bg self-stretch min-w-0 ml-auto"
      style={{ flex: "0 1 720px", gridTemplateColumns: "1fr 1fr 1.3fr 1fr 0.9fr" }}
    >
      {tiles.map((t, i) => {
        const tileCls = cn(
          "py-3.5 px-3 flex flex-col items-center text-center min-w-0",
          i < tiles.length - 1 && "border-r border-border2",
        );
        const label = (
          <SectionLabel size={14}>
            {t.onClick ? (
              <span className="relative inline-block leading-none">
                {t.label}
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 -translate-y-1/2 ml-1.5 leading-none"
                  style={{ left: "100%" }}
                >
                  <Info size={14} className="text-muted" />
                </span>
              </span>
            ) : (
              t.label
            )}
          </SectionLabel>
        );
        const body = (
          <>
            {label}
            <div className="flex-1 flex items-center justify-center">{t.value}</div>
          </>
        );
        if (t.onClick) {
          return (
            <button
              key={t.label}
              type="button"
              ref={t.btnRef}
              onClick={t.onClick}
              aria-label={`Show ${t.label.toLowerCase()} breakdown`}
              className={cn(tileCls, "bg-transparent cursor-pointer hover:bg-surface2/40 transition-colors")}
            >
              {body}
            </button>
          );
        }
        return (
          <div key={t.label} className={tileCls}>
            {body}
          </div>
        );
      })}
    </div>
  );
}

function BreakdownPanel({ profile, events }: { profile: PlayerProfile; events: PlayerDraftEvent[] }) {
  const formatBreakdown = useMemo(
    () => [...profile.formatBreakdown].sort((a, b) => b.scoreContribution - a.scoreContribution),
    [profile.formatBreakdown],
  );
  const total = formatBreakdown.reduce((s, f) => s + f.scoreContribution, 0) || 1;
  const { colorCount, comboCount, comboTrophies } = aggregate(events);
  const comboEntries = Object.entries(comboCount).sort((a, b) => b[1] - a[1]);
  const comboTotal = comboEntries.reduce((s, [, n]) => s + n, 0) || 1;
  const colorTotal = Object.values(colorCount).reduce((a, b) => a + b, 0) || 1;

  const [fmtHover, setFmtHover] = useState<string | null>(null);
  const [deckHover, setDeckHover] = useState<string | null>(null);
  const [colorHover, setColorHover] = useState<string | null>(null);

  const deckRowRefs = useRef<Record<string, HTMLDivElement | null>>({});
  useEffect(() => {
    if (deckHover) {
      deckRowRefs.current[deckHover]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [deckHover]);

  return (
    <section className="py-6 pl-10 pr-8 border-r border-border">
      <SectionLabel size={13} className="mb-3.5 text-center" style={{ width: 148 }}>POINTS BY FORMAT</SectionLabel>
      <div className="flex items-center gap-5 mb-4">
        <DonutChart
          pieHole={0.5}
          entries={formatBreakdown.map((f) => ({
            key: f.formatLabel,
            value: f.scoreContribution / total,
            color: FMT_COLORS[f.formatLabel] ?? "#5c8aff",
          }))}
          radius={56}
          strokeWidth={18}
          size={148}
          activeKey={fmtHover}
          onHoverEntry={setFmtHover}
        />
        <FormatLegend
          breakdown={formatBreakdown}
          totalScore={profile.score}
          hoveredKey={fmtHover}
          onHover={setFmtHover}
        />
      </div>

      <SectionLabel size={13} className="mt-6 mb-3 text-center" style={{ width: 148 }}>DECK COLORS</SectionLabel>
      <div className="flex items-center gap-5">
        <DonutChart
          pieHole={0.5}
          entries={comboEntries.map(([k, v]) => ({
            key: k,
            value: v,
            colors: comboColors(k),
          }))}
          radius={56}
          strokeWidth={18}
          size={148}
          activeKey={deckHover}
          onHoverEntry={setDeckHover}
        />
        <div
          className="flex-1 flex flex-col gap-1 max-h-[148px] overflow-y-auto overflow-x-hidden pr-2 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-border2 [&::-webkit-scrollbar-thumb]:rounded-full"
          style={{ scrollbarWidth: "thin", scrollbarColor: "#3b4458 transparent" }}
        >
          {comboEntries.map(([code, count]) => (
            <div
              key={code}
              ref={(el) => {
                deckRowRefs.current[code] = el;
              }}
              onMouseEnter={() => setDeckHover(code)}
              onMouseLeave={() => setDeckHover(null)}
              className={cn(
                "grid gap-2 items-center px-1.5 rounded transition-colors cursor-default",
                deckHover === code && "bg-surface2",
              )}
              style={{ gridTemplateColumns: "auto 1fr 38px 36px" }}
            >
              <Pips colors={code} size={12} />
              <span className="font-display text-[13px] tracking-[0.06em]">
                {colorsDisplayName(code)}
              </span>
              <TrophyCount
                count={comboTrophies[code] ?? 0}
                size="sm"
                fixedDigits={2}
                className="text-muted justify-self-end"
              />
              <span className="mono text-[12px] text-muted text-right">
                ×{count}
              </span>
            </div>
          ))}
        </div>
      </div>

      <SectionLabel size={13} className="mt-6 mb-3 text-center" style={{ width: 148 }}>COLORS PLAYED</SectionLabel>
      <div className="flex items-center gap-5">
        <DonutChart
          pieHole={0.5}
          entries={Object.entries(colorCount)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => ({ key: k, value: v, color: COLOR_STROKES[k] }))}
          radius={56}
          strokeWidth={18}
          size={148}
          activeKey={colorHover}
          onHoverEntry={setColorHover}
        />
        <div className="flex-1 flex flex-col gap-1 pr-4">
          {COLOR_KEYS.map((c) => {
            const pct = (colorCount[c] / colorTotal) * 100;
            return (
              <div
                key={c}
                onMouseEnter={() => setColorHover(c)}
                onMouseLeave={() => setColorHover(null)}
                className={cn(
                  "grid gap-2 items-center px-1.5 -mx-1.5 rounded transition-colors cursor-default",
                  colorHover === c && "bg-surface2",
                )}
                style={{ gridTemplateColumns: "auto 1fr 44px" }}
              >
                <Pip c={c} size={12} />
                <span className="font-display text-[13px] tracking-[0.06em]">
                  {COLOR_NAMES[c]}
                </span>
                <span className="mono text-[12px] text-muted text-right">
                  {pct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FormatLegend({
  breakdown,
  totalScore,
  hoveredKey,
  onHover,
}: {
  breakdown: PlayerFormatBreakdown[];
  totalScore: number;
  hoveredKey?: string | null;
  onHover?: (key: string | null) => void;
}) {
  return (
    <div className="flex-1 flex flex-col">
      {breakdown.map((f, i) => {
        const pct = totalScore ? (f.scoreContribution / totalScore) * 100 : 0;
        return (
          <div
            key={f.formatLabel}
            onMouseEnter={onHover ? () => onHover(f.formatLabel) : undefined}
            onMouseLeave={onHover ? () => onHover(null) : undefined}
            className={cn(
              "grid items-center py-[5px] gap-2.5 px-1.5 -mx-1.5 rounded transition-colors cursor-default",
              hoveredKey === f.formatLabel && "bg-surface2",
            )}
            style={{ gridTemplateColumns: "1fr 38px 64px 44px" }}
          >
            <span
              className="font-display text-[13px] tracking-[0.06em]"
              style={{ color: FMT_COLORS[f.formatLabel] ?? "#5c8aff" }}
            >
              {shortFormat(f.formatLabel)}
            </span>
            <TrophyCount
              count={f.trophies}
              size="sm"
              fixedDigits={2}
              className="text-muted justify-self-end"
            />
            <Record
              mono
              wins={f.wins}
              losses={f.losses}
              className="mono text-[11px] text-right text-muted"
            />
            <span
              className={cn(
                "font-display text-[14px] text-right",
                pct > 0 ? "text-green" : "text-muted",
              )}
            >
              {fmtPts(f.scoreContribution)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function DraftLogDesktop({
  events,
  filtered,
  formatFilter,
  setFormatFilter,
  colorsFilter,
  setColorsFilter,
  colorOptions,
  formatOptions,
  setEndDate,
}: {
  events: PlayerDraftEvent[];
  filtered: PlayerDraftEvent[];
  formatFilter: string;
  setFormatFilter: (v: string) => void;
  colorsFilter: string;
  setColorsFilter: (v: string) => void;
  colorOptions: FilterOption[];
  formatOptions: FilterOption[];
  setEndDate: string | null;
}) {
  const sectionRef = useRef<HTMLElement>(null);
  const scrollToTop = () =>
    sectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <section ref={sectionRef} className="py-6 px-10">
      <div className="flex justify-between items-center">
        <SectionLabel size={13}>
          EVENT LOG · {filtered.length === events.length ? "ALL" : `${filtered.length} OF ${events.length}`}
        </SectionLabel>
        <div className="flex gap-2">
          <FilterDropdown
            label="FORMAT"
            value={formatFilter}
            onChange={setFormatFilter}
            options={formatOptions}
            renderValue={renderFormatOption}
            renderOption={renderFormatOption}
          />
          <FilterDropdown
            label="COLORS"
            value={colorsFilter}
            onChange={setColorsFilter}
            options={colorOptions}
            renderValue={renderColorOption}
            renderOption={renderColorOption}
          />
        </div>
      </div>

      <div
        className="mt-3 grid gap-x-3 items-stretch"
        style={{ gridTemplateColumns: "30px 110px max-content 1fr 90px 14px" }}
      >
        {filtered.map((e, i) => {
          const isFB = isFlashbackEvent(e.finishedAt, setEndDate);
          const prev = filtered[i - 1];
          const next = filtered[i + 1];
          const showBoundary = !isFB && !!prev && isFlashbackEvent(prev.finishedAt, setEndDate);
          const hideBottomBorder =
            isFB && !!next && !isFlashbackEvent(next.finishedAt, setEndDate);
          return (
            <React.Fragment key={e.eventId}>
              {showBoundary && <FlashbackDivider variant="desktop" />}
              <EventLogRow event={e} variant="desktop" hideBottomBorder={hideBottomBorder} />
            </React.Fragment>
          );
        })}
        {filtered.length === 0 && (
          <div className="p-6 text-center text-muted font-display tracking-[0.2em] col-span-full">
            NO EVENTS MATCH FILTER
          </div>
        )}
        <GoToTopButton onClick={scrollToTop} />
      </div>
    </section>
  );
}

function GoToTopButton({
  onClick,
  threshold = 600,
  compact = false,
}: {
  onClick: () => void;
  threshold?: number;
  compact?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > threshold);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [threshold]);
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Go to top"
      className={cn(
        "fixed z-30 left-1/2 -translate-x-1/2 bottom-4 md:bottom-6 inline-flex items-center gap-2 bg-surface border border-border2 text-text font-display tracking-[0.18em] shadow-lg cursor-pointer transition-opacity hover:bg-surface2",
        compact ? "px-3 py-2 text-[11px]" : "px-4 py-2.5 text-[12px]",
        visible ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      <ArrowUp size={compact ? 14 : 14} />
      TOP
    </button>
  );
}

function FormatTagPill({ tag }: { tag: { label: string; tone: "midweek" | "open" | "alchemy" } }) {
  if (tag.tone === "alchemy") {
    return (
      <img
        src="/leaderboard/alchemy.png"
        alt={tag.label}
        className="h-6 w-auto object-contain"
      />
    );
  }
  const toneCls =
    tag.tone === "midweek"
      ? "border-[#a86bff] text-[#a86bff]"
      : "border-[#ffc63a] text-[#ffc63a]";
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 bg-bg border font-display text-[11px] tracking-[0.2em] leading-none uppercase whitespace-nowrap",
        toneCls,
      )}
    >
      {tag.label}
    </span>
  );
}

function FlashbackDivider({ variant }: { variant: "desktop" | "mobile" }) {
  const mxClass = variant === "mobile" ? "-mx-[18px]" : "-mx-2";
  const spanCls = variant === "desktop" ? "col-span-full" : "";
  return (
    <div className={cn("relative my-1 border-t border-teal", mxClass, spanCls)}>
      <span className="absolute left-1/2 -translate-x-1/2 -top-[9px] px-2 py-0.5 bg-bg border border-teal text-teal font-display text-[11px] tracking-[0.2em] leading-none">
        FLASHBACK
      </span>
    </div>
  );
}

function EventLogRow({
  event: e,
  variant,
  hideBottomBorder = false,
}: {
  event: PlayerDraftEvent;
  variant: "desktop" | "mobile";
  hideBottomBorder?: boolean;
}) {
  const href = e.externalUrl ?? null;
  const linkClass = href ? "cursor-pointer transition-colors hover:bg-surface2 no-underline text-inherit" : "";
  const isPod = e.format === "PodDraft";
  const podWithoutDeck = isPod && !e.colors;
  const formatLabel = isPod && e.eventName ? e.eventName.toUpperCase() : prettyFormat(e.format).toUpperCase();
  const tag = isPod ? null : formatTag(e.format, e.expansion);
  const borderCls = hideBottomBorder ? "" : "border-b border-border";

  if (variant === "desktop") {
    const inner = (
      <>
        <span className="text-right pr-1">
          {e.isTrophy && <Trophy size={18} color="#ffc63a" />}
        </span>
        <span className="text-[12px] text-muted text-center">{fmtShortDate(eventDate(e))}</span>
        <span className="flex items-center justify-between gap-2 min-w-0">
          <span className="font-display text-[16px] tracking-[0.08em] whitespace-nowrap">{formatLabel}</span>
          {tag && <FormatTagPill tag={tag} />}
        </span>
        {podWithoutDeck ? (
          <span className="text-[12px] text-muted">Deck not submitted</span>
        ) : (() => {
          const { name, splash } = deckColorParts(e.colors);
          return (
            <span className="grid items-center" style={{ gridTemplateColumns: "100px 60px 1fr" }}>
              <Pips colors={e.colors} size={14} flat />
              <span
                className="text-[12px] text-muted"
                style={splash ? undefined : { gridColumn: "span 2" }}
              >
                {name}
              </span>
              {splash && <span className="text-[12px] text-muted">{splash}</span>}
            </span>
          );
        })()}
        <Record
          mono
          wins={e.wins}
          losses={e.losses}
          color={e.isTrophy ? "#2ee85c" : "#e6ecf5"}
          className="text-right font-display text-[22px]"
        />
        <span className="flex justify-center text-dim">
          {href && <ExternalLink size={14} aria-hidden="true" />}
        </span>
      </>
    );
    const cls = cn(
      "grid gap-x-3 py-[6px] px-2 -mx-2 items-center col-span-full",
      borderCls,
      linkClass,
    );
    const style = { gridTemplateColumns: "subgrid" };
    return href ? (
      <a href={href} target="_blank" rel="noopener noreferrer" className={cls} style={style}>
        {inner}
      </a>
    ) : (
      <div className={cls} style={style}>{inner}</div>
    );
  }

  // mobile
  const inner = (
    <>
      <span>
        {e.isTrophy && <Trophy size={16} color="#ffc63a" />}
      </span>
      <div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {!podWithoutDeck && <Pips colors={e.colors} size={11} flat />}
          <span className="font-display text-[13px] tracking-[0.08em]">
            {formatLabel}
          </span>
          {tag && <FormatTagPill tag={tag} />}
        </div>
        <div className="text-[11px] text-muted mt-0.5">
          {[
            podWithoutDeck ? "Deck not submitted" : formatDeckColors(e.colors),
            fmtShortDate(eventDate(e)),
          ].filter(Boolean).join(" · ")}
        </div>
      </div>
      <span className="inline-flex items-center gap-1.5">
        <Record
          mono
          wins={e.wins}
          losses={e.losses}
          color={e.isTrophy ? "#2ee85c" : "#e6ecf5"}
          className="font-display text-[22px]"
        />
        {href && <ExternalLink size={13} className="text-dim" aria-hidden="true" />}
      </span>
    </>
  );
  const cls = cn(
    "grid gap-2.5 py-2.5 px-[18px] -mx-[18px] items-center",
    borderCls,
    linkClass,
  );
  const style = { gridTemplateColumns: "20px 1fr auto" };
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className={cls} style={style}>
      {inner}
    </a>
  ) : (
    <div className={cls} style={style}>{inner}</div>
  );
}

// ─── Mobile ────────────────────────────────────────────────────────────────

function Mobile({
  profile,
  events,
  sibling,
  sets,
  onChangeSet,
}: {
  profile: PlayerProfile;
  events: PlayerDraftEvent[];
  sibling: SiblingNav;
  sets: SetSummary[] | undefined;
  onChangeSet: (code: string) => void;
}) {
  const navigate = useNavigate();

  const [formatFilter, setFormatFilter, colorsFilter, setColorsFilter, qs] =
    useUrlFilters();

  const { chips: colorChips, otherCombos } = useColorChips(profile.setCode);
  const colorOptions = useMemo<FilterOption[]>(() => {
    const opts: FilterOption[] = [{ value: "ALL", label: "ALL COLORS" }];
    for (const c of colorChips) {
      if (c === MULTI) opts.push({ value: MULTI, label: "SOUP" });
      else if (c === OTHER) opts.push({ value: OTHER, label: "OTHER" });
      else opts.push({ value: c, label: colorsDisplayName(c) });
    }
    return opts;
  }, [colorChips]);
  const { data: availableFormatLabels } = useAvailableFormats(profile.setCode);
  const formatOptions = useMemo(() => {
    if (!availableFormatLabels) return FORMAT_OPTIONS;
    const available = new Set(availableFormatLabels);
    return FORMAT_OPTIONS.filter((opt) => {
      if (opt.value === "ALL") return true;
      const labels = FORMAT_LABEL_GROUPS[opt.value] ?? [opt.value];
      return labels.some((l) => available.has(l));
    });
  }, [availableFormatLabels]);
  const otherSet = useMemo(() => new Set(otherCombos), [otherCombos]);

  const filtered = useMemo(
    () =>
      events.filter((e) => {
        if (formatFilter !== "ALL" && !matchesFormatFilter(e.format, formatFilter)) return false;
        if (colorsFilter !== "ALL") {
          if (colorsFilter === MULTI) {
            if (effectiveColorCount(e.colors) < 4) return false;
          } else if (colorsFilter === OTHER) {
            if (effectiveColorCount(e.colors) >= 4) return false;
            if (!otherSet.has(colorsOf(e.colors))) return false;
          } else if (colorsOf(e.colors) !== colorsFilter) return false;
        }
        return true;
      }),
    [events, formatFilter, colorsFilter, otherSet]
  );

  const filtersActive = formatFilter !== "ALL" || colorsFilter !== "ALL";
  const stats: StatStripStats = useMemo(
    () =>
      filtersActive
        ? statsFromEvents(filtered)
        : { trophies: profile.trophies, events: profile.events, wins: profile.wins, losses: profile.losses, score: profile.score },
    [filtersActive, filtered, profile.trophies, profile.events, profile.wins, profile.losses, profile.score],
  );
  const wp = winPct(stats.wins, stats.losses);
  const [pointsModalOpen, setPointsModalOpen] = useState(false);
  const pointsBtnRef = useRef<HTMLButtonElement>(null);

  const eventLogRef = useRef<HTMLElement>(null);
  const scrollToTop = () =>
    eventLogRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  return (
    <div className="bg-bg text-text min-h-screen animate-fadeIn">
      <MobilePlayerHeader sibling={sibling} navigate={navigate} qs={qs} />

      <section
        className="px-[18px] pt-5 pb-4 border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center">
          <AAvatar displayName={profile.displayName} avatarUrl={profile.avatarUrl} size={84} green />
          <div className="flex-1 min-w-0 overflow-hidden ml-3">
            <h1
              className="font-display tracking-[0.03em] m-0 pl-[5px]"
              style={{
                fontSize: "clamp(20px, 7vw, 44px)",
                lineHeight: 0.95,
                wordBreak: "normal",
                overflowWrap: "normal",
              }}
            >
              {profile.displayName.toUpperCase()}
            </h1>
          </div>
          <div className="flex flex-col items-end gap-1.5 font-display tracking-[0.18em] shrink-0">
            <span style={{ marginRight: -8 }}>
              <RankBadge rank={profile.rank} size="md" />
            </span>
            {sets ? (
              <SetCodeDropdown sets={sets} activeCode={profile.setCode} onChange={onChangeSet} size="sm" />
            ) : (
              <span className="text-[18px]">{profile.setCode}</span>
            )}
          </div>
        </div>

        <div className="mt-[18px] grid grid-cols-5 gap-[5px]">
          <StatChip
            label="TROPHIES"
            value={
              <span className="flex items-center gap-[3px]">
                <Trophy size={12} color="#ffc63a" />
                {stats.trophies}
              </span>
            }
          />
          <StatChip label="EVENTS" value={stats.events} />
          <StatChip label="RECORD" value={`${stats.wins}–${stats.losses}`} />
          <StatChip label="WIN %" value={`${wp}%`} />
          <StatChip
            label="POINTS"
            value={fmtPts(stats.score)}
            accent
            onClick={() => setPointsModalOpen((o) => !o)}
            buttonRef={pointsBtnRef}
          />
        </div>
      </section>

      <MobileBreakdown profile={profile} events={events} />

      <section ref={eventLogRef} className="py-4 px-[18px]">
        <div className="flex items-center justify-between mb-2.5 gap-2">
          <SectionLabel size={12}>
            EVENT LOG · {filtered.length === events.length ? "ALL" : `${filtered.length} OF ${events.length}`}
          </SectionLabel>
        </div>
        <div className="flex items-stretch gap-2 mb-3">
          <div className="flex-1 min-w-0 flex">
            <FilterDropdown
              label="FORMAT"
              value={formatFilter}
              onChange={setFormatFilter}
              options={formatOptions}
              variant="mobile"
              renderValue={renderFormatOption}
              renderOption={renderFormatOption}
            />
          </div>
          <div className="flex-1 min-w-0 flex">
            <FilterDropdown
              label="COLORS"
              value={colorsFilter}
              onChange={setColorsFilter}
              options={colorOptions}
              variant="mobile"
              renderValue={renderColorOption}
              renderOption={renderColorOption}
            />
          </div>
        </div>
        {(() => {
          const mobileEndDate = sets?.find((s) => s.code === profile.setCode)?.endDate ?? null;
          return filtered.map((e, i) => {
            const isFB = isFlashbackEvent(e.finishedAt, mobileEndDate);
            const prev = filtered[i - 1];
            const next = filtered[i + 1];
            const showBoundary = !isFB && !!prev && isFlashbackEvent(prev.finishedAt, mobileEndDate);
            const hideBottomBorder =
              isFB && !!next && !isFlashbackEvent(next.finishedAt, mobileEndDate);
            return (
              <React.Fragment key={e.eventId}>
                {showBoundary && <FlashbackDivider variant="mobile" />}
                <EventLogRow event={e} variant="mobile" hideBottomBorder={hideBottomBorder} />
              </React.Fragment>
            );
          });
        })()}
        {filtered.length === 0 && (
          <div className="p-6 text-center text-muted font-display tracking-[0.2em] text-[12px]">
            NO EVENTS MATCH FILTER
          </div>
        )}
        <GoToTopButton onClick={scrollToTop} compact />
      </section>

      <PointsBreakdown
        open={pointsModalOpen}
        onClose={() => setPointsModalOpen(false)}
        breakdown={profile.formatBreakdown}
        anchorRef={pointsBtnRef}
      />
    </div>
  );
}

// ─── Mobile breakdown (tabbed) ─────────────────────────────────────────────

type BreakdownTab = "format" | "deckColors" | "manaPips";

const BREAKDOWN_TAB_STORAGE_KEY = "player-breakdown-tab";

function isBreakdownTab(v: unknown): v is BreakdownTab {
  return v === "format" || v === "deckColors" || v === "manaPips";
}

function MobileBreakdown({
  profile,
  events,
}: {
  profile: PlayerProfile;
  events: PlayerDraftEvent[];
}) {
  const [tab, setTab] = useState<BreakdownTab>(() => {
    if (typeof window === "undefined") return "deckColors";
    const stored = window.localStorage.getItem(BREAKDOWN_TAB_STORAGE_KEY);
    return isBreakdownTab(stored) ? stored : "deckColors";
  });
  useEffect(() => {
    window.localStorage.setItem(BREAKDOWN_TAB_STORAGE_KEY, tab);
  }, [tab]);
  return (
    <section className="border-b border-border">
      <div className="flex border-b border-border">
        <BreakdownTabButton active={tab === "format"} onClick={() => setTab("format")}>
          POINTS BY FORMAT
        </BreakdownTabButton>
        <BreakdownTabButton active={tab === "deckColors"} onClick={() => setTab("deckColors")}>
          DECK COLORS
        </BreakdownTabButton>
        <BreakdownTabButton active={tab === "manaPips"} onClick={() => setTab("manaPips")}>
          COLORS PLAYED
        </BreakdownTabButton>
      </div>
      <div className="px-[18px] py-4">
        {tab === "format" && <MobileFormatTab profile={profile} />}
        {tab === "deckColors" && <MobileDeckColorsTab events={events} />}
        {tab === "manaPips" && <MobileManaPipsTab events={events} />}
      </div>
    </section>
  );
}

function BreakdownTabButton({
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

function MobileFormatTab({ profile }: { profile: PlayerProfile }) {
  const formatBreakdown = useMemo(
    () => [...profile.formatBreakdown].sort((a, b) => b.scoreContribution - a.scoreContribution),
    [profile.formatBreakdown],
  );
  const total = formatBreakdown.reduce((s, f) => s + f.scoreContribution, 0) || 1;
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="flex items-center gap-3.5 min-h-[140px]">
      <DonutChart
        pieHole={0.5}
        entries={formatBreakdown.map((f) => ({
          key: f.formatLabel,
          value: f.scoreContribution / total,
          color: FMT_COLORS[f.formatLabel] ?? "#5c8aff",
        }))}
        radius={42}
        strokeWidth={14}
        size={108}
        activeKey={hover}
        onHoverEntry={setHover}
      />
      <div className="flex-1 flex flex-col">
        {formatBreakdown.map((f, i) => (
          <div
            key={f.formatLabel}
            onMouseEnter={() => setHover(f.formatLabel)}
            onMouseLeave={() => setHover(null)}
            className={cn(
              "grid items-center py-[5px] gap-2 px-1.5 -mx-1.5 rounded transition-colors cursor-default",
              hover === f.formatLabel && "bg-surface2",
            )}
            style={{ gridTemplateColumns: "1fr 36px 56px 36px" }}
          >
            <span
              className="font-display text-[11px] tracking-[0.06em]"
              style={{ color: FMT_COLORS[f.formatLabel] ?? "#5c8aff" }}
            >
              {shortFormat(f.formatLabel)}
            </span>
            <TrophyCount
              count={f.trophies}
              size="sm"
              fixedDigits={2}
              className="text-muted justify-self-end"
            />
            <Record
              mono
              wins={f.wins}
              losses={f.losses}
              className="mono text-[12px] text-right text-muted"
            />
            <span
              className={cn(
                "font-display text-[12px] text-right",
                f.scoreContribution > 0 ? "text-green" : "text-muted",
              )}
            >
              {fmtPts(f.scoreContribution)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MobileDeckColorsTab({ events }: { events: PlayerDraftEvent[] }) {
  const { comboCount, comboTrophies } = aggregate(events);
  const comboEntries = Object.entries(comboCount).sort((a, b) => b[1] - a[1]);
  const comboTotal = comboEntries.reduce((s, [, n]) => s + n, 0) || 1;
  const [hover, setHover] = useState<string | null>(null);
  const rowRefs = useRef<Record<string, HTMLDivElement | null>>({});
  useEffect(() => {
    if (hover) {
      rowRefs.current[hover]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [hover]);
  if (comboEntries.length === 0) {
    return <div className="font-display text-[12px] text-muted py-3 min-h-[140px]">NO EVENTS YET</div>;
  }
  return (
    <div className="flex items-center gap-3.5 min-h-[140px]">
      <DonutChart
        pieHole={0.5}
        entries={comboEntries.map(([k, v]) => ({
          key: k,
          value: v,
          colors: comboColors(k),
        }))}
        radius={42}
        strokeWidth={14}
        size={108}
        activeKey={hover}
        onHoverEntry={setHover}
      />
      <div
        className="flex-1 flex flex-col gap-1 max-h-[126px] overflow-y-auto overflow-x-hidden pr-2 [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-border2 [&::-webkit-scrollbar-thumb]:rounded-full"
        style={{ scrollbarWidth: "thin", scrollbarColor: "#3b4458 transparent" }}
      >
        {comboEntries.map(([code, count]) => (
          <div
            key={code}
            ref={(el) => {
              rowRefs.current[code] = el;
            }}
            onMouseEnter={() => setHover(code)}
            onMouseLeave={() => setHover(null)}
            className={cn(
              "grid gap-2 items-center px-1.5 rounded transition-colors cursor-default min-h-[22px]",
              hover === code && "bg-surface2",
            )}
            style={{ gridTemplateColumns: "auto 1fr 38px 36px" }}
          >
            <Pips colors={code} size={11} />
            <span className="font-display text-[12px] tracking-[0.06em]">
              {colorsDisplayName(code)}
            </span>
            <TrophyCount
              count={comboTrophies[code] ?? 0}
              size="sm"
              fixedDigits={2}
              className="text-muted justify-self-end"
            />
            <span className="mono text-[12px] text-muted text-right">
              ×{count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MobileManaPipsTab({ events }: { events: PlayerDraftEvent[] }) {
  const { colorCount } = aggregate(events);
  const colorTotal = Object.values(colorCount).reduce((a, b) => a + b, 0) || 1;
  const [hover, setHover] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center gap-6 min-h-[140px]">
        <DonutChart
          pieHole={0.5}
          entries={Object.entries(colorCount)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => ({ key: k, value: v, color: COLOR_STROKES[k] }))}
          radius={42}
          strokeWidth={14}
          size={108}
          activeKey={hover}
          onHoverEntry={setHover}
        />
        <div className="flex-1 flex flex-col gap-1 pr-4">
          {COLOR_KEYS.map((c) => {
            const pct = (colorCount[c] / colorTotal) * 100;
            return (
              <div
                key={c}
                onMouseEnter={() => setHover(c)}
                onMouseLeave={() => setHover(null)}
                className={cn(
                  "grid gap-2 items-center px-1.5 -mx-1.5 rounded transition-colors cursor-default min-h-[22px]",
                  hover === c && "bg-surface2",
                )}
                style={{ gridTemplateColumns: "auto 1fr 40px" }}
              >
                <Pip c={c} size={11} />
                <span className="font-display text-[12px] tracking-[0.06em]">
                  {COLOR_NAMES[c]}
                </span>
                <span className="mono text-[12px] text-muted text-right">
                  {pct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function BackButton({
  onClick,
  compact = false,
  inline = false,
}: {
  onClick: () => void;
  compact?: boolean;
  /** When true, drop the bottom margin so the button can sit in a flex row alongside other controls. */
  inline?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "bg-transparent border-none text-muted font-display leading-none cursor-pointer flex items-center transition-colors hover:text-text",
        compact ? "text-[12px] tracking-[0.15em] gap-1.5" : "text-[14px] tracking-[0.18em] gap-1.5",
        !compact && !inline && "mb-3.5",
      )}
    >
      <ChevronLeft size={compact ? 14 : 16} className="shrink-0" /> {compact ? "BACK" : "BACK TO LEADERBOARD"}
    </button>
  );
}

function SiblingNavButtons({
  sibling,
  qs = "",
  compact = false,
}: {
  sibling: SiblingNav;
  qs?: string;
  compact?: boolean;
}) {
  const baseCls = cn(
    "bg-transparent border-none font-display tracking-[0.15em] leading-none flex items-center gap-1.5 transition-colors",
    compact ? "text-[12px]" : "text-[14px]",
    "cursor-pointer hover:text-text no-underline text-muted",
  );
  const disabledCls = "opacity-30 cursor-default pointer-events-none text-muted";
  const toFor = (s: string | null) =>
    s ? { pathname: `/${sibling.setCode}/player/${s}`, search: qs } : null;
  const prevTo = toFor(sibling.prevSlug);
  const nextTo = toFor(sibling.nextSlug);
  return (
    <div
      data-popover-keep-open
      className={cn("flex items-center", compact ? "gap-3" : "gap-5")}
    >
      {prevTo ? (
        <Link to={prevTo} className={baseCls} aria-label="Previous player">
          <ChevronLeft size={16} className="shrink-0" /> PREV
        </Link>
      ) : (
        <span className={cn(baseCls, disabledCls)} aria-disabled="true">
          <ChevronLeft size={16} className="shrink-0" /> PREV
        </span>
      )}
      {nextTo ? (
        <Link to={nextTo} className={baseCls} aria-label="Next player">
          NEXT <ChevronRight size={16} className="shrink-0" />
        </Link>
      ) : (
        <span className={cn(baseCls, disabledCls)} aria-disabled="true">
          NEXT <ChevronRight size={16} className="shrink-0" />
        </span>
      )}
    </div>
  );
}
