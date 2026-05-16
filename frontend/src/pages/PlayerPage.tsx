import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowUp, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { BsAsterisk, BsPaletteFill } from "react-icons/bs";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { AAvatar, ALogo, SetGlyph, Trophy, fmtPts } from "../components/Brand";
import { Pip, Pips } from "../components/ManaPips";
import { StatChip } from "../components/StatChip";
import { FilterDropdown } from "../components/FilterDropdown";
import { SectionLabel } from "../components/SectionLabel";
import { Record } from "../components/Record";
import { DonutChart } from "../components/DonutChart";
import { ErrorState } from "../components/ErrorState";
import { TrophyCount } from "../components/TrophyCount";
import { SetCodeDropdown } from "../components/SetCodeDropdown";

import { useAvailableFormats, useColorChips, useDraftEvents, useLeaderboard, usePlayerProfile, useSets } from "../data/hooks";
import { colorsOf, effectiveColorCount, fmtShortDate, mainColors, prettyFormat, winPct } from "../data/utils";
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
  const { data: profile, isLoading, error } = usePlayerProfile(slug, setCode);
  const { data: events } = useDraftEvents(slug, setCode);
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

  return isMobile ? (
    <Mobile profile={profile} events={events ?? []} sibling={sibling} sets={sets} onChangeSet={onChangeSet} />
  ) : (
    <Desktop profile={profile} events={events ?? []} sibling={sibling} sets={sets} onChangeSet={onChangeSet} />
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
  return (
    <header className="py-3 px-[18px] border-b border-border grid grid-cols-3 items-center">
      <BackButton
        onClick={() => navigate({ pathname: `/${sibling.setCode}`, search: qs })}
        compact
      />
      <Link to="/" className="flex justify-center no-underline" aria-label="Home">
        <div className="flex items-center overflow-visible" style={{ height: 14 }}>
          <ALogo size={22} />
        </div>
      </Link>
      <div className="justify-self-end">
        <SiblingNavButtons sibling={sibling} qs={qs} compact />
      </div>
    </header>
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
              className="grid gap-3 py-[11px] border-b border-border items-center"
              style={{ gridTemplateColumns: "30px 110px 110px 1fr 90px" }}
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
  const wp = winPct(profile.wins, profile.losses);

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

  return (
    <div className="bg-bg text-text min-h-screen animate-fadeIn">
      <AppHeader subtitle="PLAYER PROFILE" />

      <section
        className="px-10 pt-7 pb-[30px] border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center justify-between mb-3.5">
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
              <span
                className="inline-block"
                style={{
                  clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)",
                  background: "#2ee85c",
                  padding: 1,
                  minHeight: 46,
                }}
              >
                <span
                  className="flex items-center bg-surface text-green font-display tracking-[0.06em] leading-none text-[26px] px-[18px] h-full"
                  style={{
                    clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)",
                    minHeight: 44,
                  }}
                >
                  #{profile.rank}
                </span>
              </span>
            </div>
          </div>
          <StatStrip profile={profile} wp={wp} />
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
        />
      </div>
    </div>
  );
}

function StatStrip({ profile, wp }: { profile: PlayerProfile; wp: string }) {
  const valueCls = "font-display leading-none text-[clamp(26px,3vw,44px)]";
  const tiles: Array<{ label: string; value: React.ReactNode; accent?: boolean }> = [
    {
      label: "TROPHIES",
      value: (
        <span className="flex items-center gap-1.5">
          <Trophy size={26} color="#ffc63a" />
          <span className={valueCls}>{profile.trophies}</span>
        </span>
      ),
    },
    {
      label: "EVENTS",
      value: <span className={valueCls}>{profile.events}</span>,
    },
    {
      label: "RECORD",
      value: (
        <Record
          mono
          wins={profile.wins}
          losses={profile.losses}
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
      value: (
        <span className={cn(valueCls, "text-green")}>{fmtPts(profile.score)}</span>
      ),
      accent: true,
    },
  ];
  return (
    <div
      className="grid border border-border2 bg-bg self-stretch min-w-0 ml-auto"
      style={{ flex: "0 1 720px", gridTemplateColumns: "1fr 1fr 1.3fr 1fr 0.9fr" }}
    >
      {tiles.map((t, i) => (
        <div
          key={t.label}
          className={cn(
            "py-3.5 px-3 flex flex-col items-center text-center min-w-0",
            i < tiles.length - 1 && "border-r border-border2",
          )}
        >
          <SectionLabel size={14}>{t.label}</SectionLabel>
          <div className="flex-1 flex items-center justify-center">{t.value}</div>
        </div>
      ))}
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
}: {
  events: PlayerDraftEvent[];
  filtered: PlayerDraftEvent[];
  formatFilter: string;
  setFormatFilter: (v: string) => void;
  colorsFilter: string;
  setColorsFilter: (v: string) => void;
  colorOptions: FilterOption[];
  formatOptions: FilterOption[];
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

      <div className="mt-3">
        {filtered.map((e) => (
          <EventLogRow key={e.eventId} event={e} variant="desktop" />
        ))}
        {filtered.length === 0 && (
          <div className="p-6 text-center text-muted font-display tracking-[0.2em]">
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

function EventLogRow({ event: e, variant }: { event: PlayerDraftEvent; variant: "desktop" | "mobile" }) {
  const href = e.externalUrl ?? null;
  const linkClass = href ? "cursor-pointer transition-colors hover:bg-surface2 no-underline text-inherit" : "";
  const isPod = e.format === "PodDraft";

  if (variant === "desktop") {
    const inner = (
      <>
        <span className="text-center">
          {e.isTrophy ? <Trophy size={18} color="#ffc63a" /> : <span className="text-dim">·</span>}
        </span>
        <span className="text-[11px] text-muted">{fmtShortDate(e.finishedAt)}</span>
        <span className="font-display text-[14px] tracking-[0.08em]">
          {prettyFormat(e.format).toUpperCase()}
        </span>
        {isPod ? (
          <span />
        ) : (() => {
          const { name, splash } = deckColorParts(e.colors);
          return (
            <span className="grid items-center" style={{ gridTemplateColumns: "100px 60px 1fr" }}>
              <Pips colors={e.colors} size={13} />
              <span
                className="text-[11px] text-muted"
                style={splash ? undefined : { gridColumn: "span 2" }}
              >
                {name}
              </span>
              {splash && <span className="text-[11px] text-muted">{splash}</span>}
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
          {href && <ExternalLink size={11} aria-hidden="true" />}
        </span>
      </>
    );
    const cls = cn(
      "grid gap-3 py-[11px] px-2 -mx-2 border-b border-border items-center",
      linkClass,
    );
    const style = { gridTemplateColumns: "30px 110px 110px 1fr 90px 14px" };
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
        {e.isTrophy ? <Trophy size={16} color="#ffc63a" /> : <span className="text-dim">·</span>}
      </span>
      <div>
        <div className="flex items-center gap-1.5">
          {!isPod && <Pips colors={e.colors} size={11} />}
          <span className="font-display text-[13px] tracking-[0.08em]">
            {prettyFormat(e.format).toUpperCase()}
          </span>
        </div>
        <div className="text-[11px] text-muted mt-0.5">
          {isPod ? fmtShortDate(e.finishedAt) : `${formatDeckColors(e.colors)} · ${fmtShortDate(e.finishedAt)}`}
        </div>
      </div>
      <span className="inline-flex items-center gap-1.5">
        <Record
          mono
          wins={e.wins}
          losses={e.losses}
          color={e.isTrophy ? "#2ee85c" : "#e6ecf5"}
          className="mono text-[14px] font-semibold"
        />
        {href && <ExternalLink size={10} className="text-dim" aria-hidden="true" />}
      </span>
    </>
  );
  const cls = cn(
    "grid gap-2.5 py-2.5 px-2 -mx-2 border-b border-border items-center",
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
  const wp = winPct(profile.wins, profile.losses);

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
            <span
              className="inline-block"
              style={{
                clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)",
                background: "#2ee85c",
                padding: 1,
                minHeight: 38,
                marginRight: -8,
              }}
            >
              <span
                className="flex items-center bg-surface text-green font-display tracking-[0.06em] leading-none text-[22px] px-[14px] h-full"
                style={{
                  clipPath: "polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%)",
                  minHeight: 36,
                }}
              >
                #{profile.rank}
              </span>
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
                {profile.trophies}
              </span>
            }
            mono={false}
          />
          <StatChip label="EVENTS" value={profile.events} />
          <StatChip label="RECORD" value={`${profile.wins}–${profile.losses}`} />
          <StatChip label="WIN %" value={`${wp}%`} />
          <StatChip label="POINTS" value={fmtPts(profile.score)} accent mono={false} />
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
        {filtered.map((e) => (
          <EventLogRow key={e.eventId} event={e} variant="mobile" />
        ))}
        {filtered.length === 0 && (
          <div className="p-6 text-center text-muted font-display tracking-[0.2em] text-[12px]">
            NO EVENTS MATCH FILTER
          </div>
        )}
        <GoToTopButton onClick={scrollToTop} compact />
      </section>
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
        "bg-transparent border-none text-muted font-display text-[12px] leading-none cursor-pointer flex items-center transition-colors hover:text-text",
        compact ? "tracking-[0.15em] gap-1.5" : "tracking-[0.18em] gap-1",
        !compact && !inline && "mb-3.5",
      )}
    >
      <ChevronLeft size={14} className="shrink-0 -mt-px" /> {compact ? "BACK" : "BACK TO LEADERBOARD"}
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
    "bg-transparent border-none font-display tracking-[0.15em] leading-none flex items-center gap-1.5 text-[12px] transition-colors",
    "cursor-pointer hover:text-text no-underline text-muted",
  );
  const disabledCls = "opacity-30 cursor-default pointer-events-none text-muted";
  const toFor = (s: string | null) =>
    s ? { pathname: `/${sibling.setCode}/player/${s}`, search: qs } : null;
  const prevTo = toFor(sibling.prevSlug);
  const nextTo = toFor(sibling.nextSlug);
  return (
    <div className={cn("flex items-center", compact ? "gap-2" : "gap-3")}>
      {prevTo ? (
        <Link to={prevTo} className={baseCls} aria-label="Previous player">
          <ChevronLeft size={14} className="shrink-0 -mt-px" /> PREV
        </Link>
      ) : (
        <span className={cn(baseCls, disabledCls)} aria-disabled="true">
          <ChevronLeft size={14} className="shrink-0 -mt-px" /> PREV
        </span>
      )}
      <span className="text-dim text-[12px]">·</span>
      {nextTo ? (
        <Link to={nextTo} className={baseCls} aria-label="Next player">
          NEXT <ChevronRight size={14} className="shrink-0 -mt-px" />
        </Link>
      ) : (
        <span className={cn(baseCls, disabledCls)} aria-disabled="true">
          NEXT <ChevronRight size={14} className="shrink-0 -mt-px" />
        </span>
      )}
    </div>
  );
}
