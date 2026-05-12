import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import React, { Fragment, useEffect, useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";
import { BsAsterisk, BsPaletteFill } from "react-icons/bs";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { ArrowRight, SetGlyph, Trophy } from "../components/Brand";
import { Footer } from "../components/Footer";
import { Pip, Pips } from "../components/ManaPips";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { FilterDropdown } from "../components/FilterDropdown";
import { ColorsSwitcher } from "../components/ColorsSwitcher";
import { LeaderboardSidebar } from "../components/LeaderboardSidebar";
import { DEFAULT_SORT, LeaderboardColumnHeader, LeaderboardTable, sortRows } from "../components/LeaderboardTable";
import type { SortDir, SortKey, SortState } from "../components/LeaderboardTable";
import { SectionLabel } from "../components/SectionLabel";
import { ChamferedButton } from "../components/ChamferedButton";
import { Record } from "../components/Record";
import { DonutChart } from "../components/DonutChart";
import { TrophyCount } from "../components/TrophyCount";

import {
  useColorChips,
  useColorsLeaderboard,
  useDraftEvents,
  useFormatLeaderboard,
  useIdlePrefetchOtherSets,
  useIdlePrefetchTopPlayers,
  useLeaderboard,
  useOtherColorsLeaderboard,
  usePlayerProfile,
  useSets,
} from "../data/hooks";
import { colorsOf, effectiveColorCount, fmtRange, lastUpdated, prettyFormat, relativeTime, sumEvents, weekOfSet, winPct } from "../data/utils";
import { colorsDisplayName, FORMAT_OPTIONS, matchesFormatFilter, MULTI, OTHER } from "../data/filters";
import { FMT_COLORS, FMT_DEFAULT_COLOR, renderFormatOption, shortFormat } from "../data/format-display";
import { guildLogoTransform, guildSvgUrl } from "../data/guild-art";
import { cn } from "../lib/utils";
import type { LeaderboardRow, PlayerDraftEvent, PlayerFormatBreakdown, SetSummary } from "../types/leaderboard";
import type { LeaderboardTableRow } from "../components/LeaderboardTable";

// ─── Page entry ────────────────────────────────────────────────────────────

export function LeaderboardPage() {
  const params = useParams<{ setCode?: string }>();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { data: sets } = useSets();
  const activeSet = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const setMeta = sets?.find((s) => s.code === activeSet);

  const liveSetCode = sets?.find((s) => s.isActive)?.code;
  // Filters live in the URL as query params (?format=Premier or ?colors=WR).
  // Per spec they're mutually exclusive, so picking a non-ALL value in one
  // clears the other.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    if (params.setCode && liveSetCode && params.setCode === liveSetCode) {
      navigate({ pathname: "/", search: searchParams.toString() }, { replace: true });
    }
  }, [params.setCode, liveSetCode, navigate, searchParams]);
  const format = searchParams.get("format") ?? "ALL";
  const colors = searchParams.get("colors") ?? "ALL";
  const colorsMode = colors !== "ALL";
  const formatMode = !colorsMode && format !== "ALL";

  const setFormat = (v: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "ALL") {
        next.delete("format");
      } else {
        next.set("format", v);
        next.delete("colors");
      }
      return next;
    });
  };
  const setColors = (v: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (v === "ALL") {
        next.delete("colors");
      } else {
        next.set("colors", v);
        next.delete("format");
      }
      return next;
    });
  };

  const { chips: colorChips, otherCombos } = useColorChips(activeSet);

  const otherMode = colorsMode && colors === OTHER;
  const namedColorsMode = colorsMode && colors !== OTHER;

  const lb = useLeaderboard(colorsMode || formatMode ? undefined : activeSet);
  const fmtLb = useFormatLeaderboard(
    formatMode ? activeSet : undefined,
    formatMode ? format : undefined,
  );
  const colorsLb = useColorsLeaderboard(
    namedColorsMode ? activeSet : undefined,
    namedColorsMode ? colors : undefined,
  );
  const otherLb = useOtherColorsLeaderboard(
    otherMode ? activeSet : undefined,
    otherMode ? otherCombos : undefined,
  );

  const active = otherMode
    ? otherLb
    : namedColorsMode
      ? colorsLb
      : formatMode
        ? fmtLb
        : lb;
  const baseRows: LeaderboardTableRow[] | undefined = active.data;
  const isLoading = active.isLoading;
  const error = active.error as Error | null;

  const sort = readSortFromParams(searchParams);
  const rows = useMemo(
    () => (baseRows ? sortRows(baseRows, sort) : baseRows),
    [baseRows, sort.key, sort.dir],
  );

  const onSort = (key: SortKey) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      const curKey = (next.get("sort") as SortKey | null) ?? DEFAULT_SORT.key;
      const curDir = (next.get("dir") as SortDir | null) ?? DEFAULT_SORT.dir;
      const dir: SortDir =
        curKey === key ? (curDir === "desc" ? "asc" : "desc") : "desc";
      if (key === DEFAULT_SORT.key && dir === DEFAULT_SORT.dir) {
        next.delete("sort");
        next.delete("dir");
      } else {
        next.set("sort", key);
        if (dir === "desc") next.delete("dir");
        else next.set("dir", dir);
      }
      return next;
    });
  };

  useIdlePrefetchOtherSets(activeSet, sets);
  useIdlePrefetchTopPlayers(rows);

  const filterProps: FilterRowProps = { format, setFormat, colors, setColors, colorChips };

  return isMobile ? (
    <Mobile
      activeSet={activeSet}
      sets={sets}
      rows={rows}
      isLoading={isLoading}
      error={error}
      filters={filterProps}
      colorsMode={colorsMode}
      otherCombos={otherCombos}
      searchParams={searchParams}
      sort={sort}
      onSort={onSort}
    />
  ) : (
    <Desktop
      activeSet={activeSet}
      sets={sets}
      setMeta={setMeta}
      rows={rows}
      isLoading={isLoading}
      error={error}
      filters={filterProps}
      colorsMode={colorsMode}
      otherCombos={otherCombos}
      searchParams={searchParams}
      sort={sort}
      onSort={onSort}
    />
  );
}

const SORT_KEYS: ReadonlySet<SortKey> = new Set([
  "score",
  "trophies",
  "events",
  "record",
  "winPct",
]);

function readSortFromParams(searchParams: URLSearchParams): SortState {
  const rawKey = searchParams.get("sort");
  const rawDir = searchParams.get("dir");
  const key: SortKey = rawKey && SORT_KEYS.has(rawKey as SortKey) ? (rawKey as SortKey) : DEFAULT_SORT.key;
  const dir: SortDir = rawDir === "asc" ? "asc" : "desc";
  return { key, dir };
}

interface FilterRowProps {
  format: string;
  setFormat: (v: string) => void;
  colors: string;
  setColors: (v: string) => void;
  colorChips: string[];
}

// ─── Desktop ───────────────────────────────────────────────────────────────

function Desktop({
  activeSet,
  sets,
  setMeta,
  rows,
  isLoading,
  error,
  filters,
  colorsMode: _colorsMode,
  otherCombos,
  searchParams,
  sort,
  onSort,
}: {
  activeSet: string;
  sets: SetSummary[] | undefined;
  setMeta: SetSummary | undefined;
  rows: LeaderboardTableRow[] | undefined;
  isLoading: boolean;
  error: Error | null;
  filters: FilterRowProps;
  colorsMode: boolean;
  otherCombos: string[];
  searchParams: URLSearchParams;
  sort: SortState;
  onSort: (key: SortKey) => void;
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="LEADERBOARD" />
      <SetHero
        activeSet={activeSet}
        setMeta={setMeta}
        sets={sets}
        onSelectSet={(c) => goToSet(navigate, c, sets, searchParams)}
        format={filters.format}
        colors={filters.colors}
      />
      <FilterRow {...filters} rows={rows} />

      <div className="px-5 grid gap-6" style={{ gridTemplateColumns: "1fr 320px" }}>
        <LeaderboardTable
          rows={rows}
          variant="desktop"
          loading={isLoading}
          error={error}
          sort={sort}
          onSort={onSort}
          renderExpanded={(r) => (
            <DesktopExpandedRow
              row={r}
              to={{
                pathname: `/${activeSet}/player/${r.slug}`,
                search: searchParams.toString(),
              }}
              activeFormat={filters.format}
              activeColors={filters.colors}
              otherCombos={otherCombos}
            />
          )}
        />
        <div className="pt-4">
          <LeaderboardSidebar
            setCode={activeSet}
            colors={filters.colors}
            format={filters.format}
            otherCombos={otherCombos}
            onColorsSelect={filters.setColors}
            searchParams={searchParams}
          />
        </div>
      </div>
      <Footer className="mt-auto px-10 pt-5 pb-3" />
    </div>
  );
}

function SetHero({
  activeSet,
  setMeta,
  sets,
  onSelectSet,
  format,
  colors,
}: {
  activeSet: string;
  setMeta: SetSummary | undefined;
  sets: SetSummary[] | undefined;
  onSelectSet: (code: string) => void;
  format: string;
  colors: string;
}) {
  const week = weekOfSet(setMeta);
  const isActive = setMeta?.isActive ?? false;
  const filterActive = format !== "ALL" || colors !== "ALL";
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
      {sets && (
        <SetSwitcherDesktop sets={sets} activeCode={activeSet} onChange={onSelectSet} />
      )}
      {filterActive && <FilterHero format={format} colors={colors} />}
    </div>
  );
}

function ColorsHeroGlyph({ code }: { code: string }) {
  return (
    <span
      className="shrink-0 inline-flex items-center justify-center"
      style={{ width: 48, height: 48 }}
    >
      <ColorsHeroGlyphInner code={code} />
    </span>
  );
}

function ColorsHeroGlyphInner({ code }: { code: string }) {
  if (code === MULTI) {
    return <BsPaletteFill size={36} aria-hidden="true" />;
  }
  if (code === OTHER) {
    return <BsAsterisk size={32} aria-hidden="true" />;
  }
  const url = guildSvgUrl(code);
  if (url) {
    return (
      <img
        src={url}
        alt=""
        aria-hidden="true"
        className="block"
        style={{ height: 44, width: 44, transform: guildLogoTransform(code) }}
      />
    );
  }
  if (code.length === 1 && "WUBRG".includes(code)) {
    return <Pip c={code as "W" | "U" | "B" | "R" | "G"} size={32} />;
  }
  const isTri = code.length === 3 && [...code].every((c) => "WUBRG".includes(c));
  if (isTri) {
    const [top, left, right] = [...code] as Array<"W" | "U" | "B" | "R" | "G">;
    return (
      <span className="inline-flex flex-col items-center" style={{ gap: 2 }}>
        <Pip c={top} size={20} />
        <span className="inline-flex" style={{ gap: 2 }}>
          <Pip c={left} size={20} />
          <Pip c={right} size={20} />
        </span>
      </span>
    );
  }
  return <Pips colors={code} size={22} />;
}

function FilterHero({ format, colors }: { format: string; colors: string }) {
  const colorsActive = colors !== "ALL";
  if (colorsActive) {
    const name = colorsDisplayName(colors);
    return (
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="flex items-center gap-4 whitespace-nowrap">
          <ColorsHeroGlyph code={colors} />
          <span
            className="font-display tracking-[0.06em]"
            style={{ fontSize: 36, lineHeight: 1 }}
          >
            {name}
          </span>
        </div>
      </div>
    );
  }
  const opt = FORMAT_OPTIONS.find((o) => o.value === format);
  const label = opt?.label ?? format.toUpperCase();
  const color = FMT_COLORS[format] ?? FMT_DEFAULT_COLOR;
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <span
        className="font-display tracking-[0.06em] whitespace-nowrap"
        style={{ fontSize: 36, lineHeight: 1, color }}
      >
        {label}
      </span>
    </div>
  );
}

function FilterRow({
  format,
  setFormat,
  colors,
  setColors,
  colorChips,
  rows,
}: FilterRowProps & { rows: LeaderboardTableRow[] | undefined }) {
  return (
    <div className="px-10 py-3.5 border-b border-border flex items-center gap-4 flex-wrap">
      <FilterDropdown
        label="FORMAT"
        value={format}
        options={FORMAT_OPTIONS}
        onChange={setFormat}
        renderValue={renderFormatOption}
        renderOption={renderFormatOption}
      />
      <SectionLabel size={11}>COLORS</SectionLabel>
      <ColorsSwitcher activeCode={colors} onChange={setColors} chips={colorChips} />
      <span className="flex-1" />
      <div className="mono text-[12px] text-muted">
        {rows?.length ?? 0} PLAYERS · {sumEvents(rows)} EVENTS · UPDATED {lastUpdated(rows)}
      </div>
    </div>
  );
}

// ─── Mobile ────────────────────────────────────────────────────────────────

function Mobile({
  activeSet,
  sets,
  rows,
  isLoading,
  error,
  filters,
  colorsMode: _colorsMode,
  otherCombos,
  searchParams,
  sort,
  onSort,
}: {
  activeSet: string;
  sets: SetSummary[] | undefined;
  rows: LeaderboardTableRow[] | undefined;
  isLoading: boolean;
  otherCombos: string[];
  error: Error | null;
  filters: FilterRowProps;
  colorsMode: boolean;
  searchParams: URLSearchParams;
  sort: SortState;
  onSort: (key: SortKey) => void;
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col overflow-x-hidden animate-fadeIn">
      <div className="sticky top-0 z-10 bg-bg">
        <AppHeader subtitle="LEADERBOARD" />

        <div className="px-3 py-2 border-b border-border bg-surface flex items-stretch gap-2">
          <div className="basis-[60%] min-w-0 flex">
            <FilterDropdown
              label="FORMAT"
              value={filters.format}
              options={FORMAT_OPTIONS}
              onChange={filters.setFormat}
              variant="mobile"
              renderValue={renderFormatOption}
              renderOption={renderFormatOption}
            />
          </div>
          {sets && (
            <div className="basis-[40%] min-w-0">
              <SetSwitcherMobile
                sets={sets}
                activeCode={activeSet}
                onChange={(code) => goToSet(navigate, code, sets, searchParams)}
              />
            </div>
          )}
        </div>
        <div className="px-3 py-1.5 border-b border-border bg-bg">
          <ColorsSwitcher
            activeCode={filters.colors}
            onChange={filters.setColors}
            chips={filters.colorChips}
            variant="mobile"
          />
        </div>
        {/* Column header is part of the sticky chrome so it stays pinned with the
            rest of the page chrome as rows scroll under it. */}
        <LeaderboardColumnHeader variant="mobile" sort={sort} onSort={onSort} />
      </div>

      <LeaderboardTable
        rows={rows}
        variant="mobile"
        loading={isLoading}
        error={error}
        showHeader={false}
        renderExpanded={(r) => (
          <MobileExpandedRow
            row={r}
            to={{
              pathname: `/${activeSet}/player/${r.slug}`,
              search: searchParams.toString(),
            }}
            activeFormat={filters.format}
            activeColors={filters.colors}
            otherCombos={otherCombos}
          />
        )}
      />
      <Footer className="mt-auto px-4 py-4" />
    </div>
  );
}

// ─── Expanded rows ─────────────────────────────────────────────────────────

const PANEL_MIN_HEIGHT = 88;

// Debug aid — bump above 0 (e.g. 3000) to keep skeleton visible after data lands
const SKELETON_DEBUG_DELAY_MS: number = 0;

function useDelayedExpandedData(slug: string, setCode: string) {
  const profileQ = usePlayerProfile(slug, setCode);
  const eventsQ = useDraftEvents(slug, setCode);
  const [released, setReleased] = useState(SKELETON_DEBUG_DELAY_MS === 0);
  useEffect(() => {
    if (SKELETON_DEBUG_DELAY_MS === 0) return;
    const t = setTimeout(() => setReleased(true), SKELETON_DEBUG_DELAY_MS);
    return () => clearTimeout(t);
  }, []);
  return {
    profile: released ? profileQ.data : undefined,
    events: released ? eventsQ.data : undefined,
  };
}

type PlayerLinkTo = string | { pathname: string; search: string };

function DesktopExpandedRow({
  row,
  to,
  activeFormat,
  activeColors,
  otherCombos,
}: {
  row: LeaderboardTableRow;
  to: PlayerLinkTo;
  activeFormat: string;
  activeColors: string;
  otherCombos: string[];
}) {
  const { profile, events } = useDelayedExpandedData(row.slug, row.setCode);
  const { lastTrophies, biggestStreak } = useHighlights(events);
  const filtersActive = activeFormat !== "ALL" || activeColors !== "ALL";
  const filteredTrophies = useMemo(
    () => filterTrophyEvents(events, activeFormat, activeColors, otherCombos).slice(0, 3),
    [events, activeFormat, activeColors, otherCombos],
  );
  const trophiesToShow = filtersActive ? filteredTrophies : lastTrophies;

  return (
    <Link
      to={to}
      aria-label={`View ${row.displayName}'s profile`}
      className="pt-3.5 pb-4 pr-4 pl-[76px] border-t border-dashed border-border2 flex items-center gap-6 cursor-pointer transition-colors hover:bg-green/5 no-underline text-inherit"
    >
      <div className="flex-1 min-w-0 overflow-hidden"><FormatBreakdownPreview breakdown={profile?.formatBreakdown} /></div>
      <div className="flex-1 min-w-0 overflow-hidden"><MostPlayedDecks events={events} /></div>
      <div className="flex-1 min-w-0 overflow-hidden"><LastTrophyPanel data={trophiesToShow} loading={!events} activeFormat={activeFormat} activeColors={activeColors} /></div>
      <div className="flex-[0.4] min-w-0 overflow-hidden flex items-center justify-center -ml-6"><BiggestStreakPanel data={biggestStreak} loading={!events} /></div>
      <ChamferedButton>
        <span className="inline-flex items-center gap-2">
          VIEW PROFILE
          <ArrowRight size={12} />
        </span>
      </ChamferedButton>
    </Link>
  );
}

function FormatBreakdownPreview({
  breakdown,
}: {
  breakdown: PlayerFormatBreakdown[] | undefined;
}) {
  const sorted = useMemo(
    () =>
      breakdown
        ? [...breakdown]
            .filter((f) => f.events > 0)
            .sort((a, b) => b.events - a.events)
        : [],
    [breakdown],
  );
  const ready = sorted.length > 0;
  const total = ready ? Math.max(1, sorted.reduce((s, f) => s + f.events, 0)) : 1;
  const dense = sorted.length >= 4;
  const labelCls = dense ? "text-[11px]" : "text-[13px]";
  const swatchCls = dense ? "w-[11px] h-[11px]" : "w-[13px] h-[13px]";
  const numCls = dense ? "text-[11px]" : "text-[12px]";
  return (
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel className="text-subtle">FORMAT BREAKDOWN</SectionLabel>
      <div className="flex items-center gap-2.5 mt-2 min-w-0">
        <div className="shrink-0">
          <DonutChart
            entries={sorted.map((f) => ({
              key: f.formatLabel,
              value: f.events / total,
              color: FMT_COLORS[f.formatLabel] ?? FMT_DEFAULT_COLOR,
            }))}
            radius={28}
            strokeWidth={10}
            size={76}
            pieHole={0.5}
          />
        </div>
        <div
          className="grid items-center gap-x-2 gap-y-0.5 min-w-0"
          style={{ gridTemplateColumns: "auto minmax(0, 1fr) auto" }}
        >
          {ready
            ? sorted.map((f) => {
                const color = FMT_COLORS[f.formatLabel] ?? FMT_DEFAULT_COLOR;
                return (
                  <Fragment key={f.formatLabel}>
                    <span className={cn(swatchCls, "shrink-0")} style={{ background: color }} />
                    <span className={cn("font-display tracking-[0.08em] truncate", labelCls)}>
                      {shortFormat(f.formatLabel)}
                    </span>
                    <span className={cn("mono text-muted tabular-nums justify-self-end", numCls)}>
                      {f.events}
                    </span>
                  </Fragment>
                );
              })
            : SKELETON_FORMAT_ROWS.map((w, i) => (
                <Fragment key={i}>
                  <span className="w-2 h-2 bg-surface2 shrink-0" />
                  <span className="h-2.5 bg-surface2" style={{ width: w }} />
                  <span className="h-2.5 bg-surface2 justify-self-end" style={{ width: 18 }} />
                </Fragment>
              ))}
        </div>
      </div>
    </div>
  );
}

const SKELETON_FORMAT_ROWS = [70, 56, 64, 48];

function MostPlayedDecks({ events }: { events: PlayerDraftEvent[] | undefined }) {
  const top = useMemo(() => {
    if (!events || events.length === 0) return [];
    const count: Record<string, number> = {};
    const trophies: Record<string, number> = {};
    for (const e of events) {
      const c = colorsOf(e.colors);
      if (c.length === 0) continue;
      count[c] = (count[c] ?? 0) + 1;
      if (e.isTrophy) trophies[c] = (trophies[c] ?? 0) + 1;
    }
    return Object.entries(count)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([code, n]) => ({ code, count: n, trophies: trophies[code] ?? 0 }));
  }, [events]);

  return (
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel className="text-subtle">MOST PLAYED DECKS</SectionLabel>
      <div
        className="grid items-center gap-x-3 gap-y-1 mt-2 w-fit"
        style={{ gridTemplateColumns: "auto 64px auto" }}
      >
        {top.length > 0
          ? top.map((d) => (
              <Fragment key={d.code}>
                <Pips colors={d.code} size={11} />
                <span className="font-display text-[13px] tracking-[0.06em]">
                  {colorsDisplayName(d.code)}
                </span>
                <TrophyCount count={d.trophies} size="compact" className="text-muted" />
              </Fragment>
            ))
          : [50, 60, 44].map((w, i) => (
              <Fragment key={i}>
                <span className="w-[26px] h-3 bg-surface2 shrink-0" />
                <span className="h-3 bg-surface2" style={{ width: w }} />
                <span className="h-2.5 bg-surface2" style={{ width: 22 }} />
              </Fragment>
            ))}
      </div>
    </div>
  );
}

function filterTrophyEvents(
  events: PlayerDraftEvent[] | undefined,
  activeFormat: string,
  activeColors: string,
  otherCombos: string[],
): PlayerDraftEvent[] {
  if (!events) return [];
  const otherSet = new Set(otherCombos);
  const matches = events.filter((e) => {
    if (!e.isTrophy) return false;
    if (!matchesFormatFilter(e.format, activeFormat)) return false;
    if (activeColors !== "ALL") {
      if (activeColors === MULTI) {
        if (effectiveColorCount(e.colors) < 4) return false;
      } else if (activeColors === OTHER) {
        if (effectiveColorCount(e.colors) >= 4) return false;
        if (!otherSet.has(colorsOf(e.colors))) return false;
      } else if (colorsOf(e.colors) !== activeColors) return false;
    }
    return true;
  });
  return matches.sort((a, b) => (b.finishedAt ?? "").localeCompare(a.finishedAt ?? ""));
}

interface StreakData { count: number; format: string }

function useHighlights(events: PlayerDraftEvent[] | undefined): {
  lastTrophies: PlayerDraftEvent[];
  biggestStreak: StreakData | null;
} {
  return useMemo(() => {
    if (!events || events.length === 0) return { lastTrophies: [], biggestStreak: null };
    const sorted = [...events].sort((a, b) =>
      (a.finishedAt ?? "").localeCompare(b.finishedAt ?? ""),
    );
    const lastTrophies: PlayerDraftEvent[] = [];
    for (let i = sorted.length - 1; i >= 0 && lastTrophies.length < 3; i--) {
      if (sorted[i].isTrophy) lastTrophies.push(sorted[i]);
    }
    let max = 0, cur = 0;
    let streakFormat = "";
    for (const e of sorted) {
      if (e.isTrophy) {
        cur += 1;
        if (cur > max) { max = cur; streakFormat = e.format; }
      } else {
        cur = 0;
      }
    }
    return {
      lastTrophies,
      biggestStreak: max >= 2 ? { count: max, format: streakFormat } : null,
    };
  }, [events]);
}

function LastTrophyPanel({
  data,
  loading,
  activeFormat,
  activeColors,
}: {
  data: PlayerDraftEvent[];
  loading: boolean;
  activeFormat: string;
  activeColors: string;
}) {
  const colorsActive = activeColors !== "ALL";
  const formatActive = !colorsActive && activeFormat !== "ALL";
  const filterLabel = colorsActive
    ? colorsDisplayName(activeColors)
    : formatActive
      ? activeFormat.toUpperCase()
      : null;
  const filterStyle = formatActive
    ? { color: FMT_COLORS[activeFormat] ?? FMT_DEFAULT_COLOR }
    : undefined;
  return (
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel className="text-subtle">
        LAST{filterLabel && (
          <>
            {" "}
            <span className={colorsActive ? "text-green" : ""} style={filterStyle}>
              {filterLabel}
            </span>
          </>
        )} TROPHIES
      </SectionLabel>
      <div className="flex flex-col gap-1 mt-2.5 min-w-0">
        {loading ? (
          [0, 1, 2].map((i) => (
            <div
              key={i}
              className="grid items-center gap-x-3 w-fit"
              style={{ gridTemplateColumns: "auto auto auto auto 12px" }}
            >
              <span className="w-[26px] h-3 bg-surface2 shrink-0" />
              <span className="h-3 bg-surface2" style={{ width: 50 }} />
              <span className="h-3 bg-surface2" style={{ width: 36 }} />
              <span className="h-3 bg-surface2" style={{ width: 24 }} />
              <span />
            </div>
          ))
        ) : data.length > 0 ? (
          data.map((e) => {
            const href = e.seventeenlandsEventId
              ? `https://www.17lands.com/deck/${e.seventeenlandsEventId}`
              : null;
            const onClick = href
              ? (ev: React.MouseEvent) => {
                  ev.preventDefault();
                  ev.stopPropagation();
                  window.open(href, "_blank", "noopener,noreferrer");
                }
              : undefined;
            return (
              <div
                key={e.eventId}
                onClick={onClick}
                role={href ? "link" : undefined}
                title={href ? "Open deck on 17lands" : undefined}
                className={cn(
                  "grid items-center gap-x-3 px-1.5 -mx-1.5 rounded transition-colors w-fit",
                  href && "hover:bg-surface2 cursor-pointer",
                )}
                style={{ gridTemplateColumns: "auto auto auto auto 12px" }}
              >
                <Pips colors={e.colors} size={11} />
                <span className="font-display text-[13px] tracking-[0.06em] text-muted truncate">
                  {shortFormat(e.format)}
                </span>
                <Record
                  wins={e.wins}
                  losses={e.losses}
                  mono
                  className="mono text-[12px] text-muted text-right justify-self-end"
                />
                <span className="mono text-[12px] text-dim">{relativeTime(e.finishedAt)}</span>
                <span className="flex justify-center text-subtle">
                  {href && <ExternalLink size={10} aria-hidden="true" />}
                </span>
              </div>
            );
          })
        ) : (
          <div className="mono text-[12px] text-muted">NONE YET</div>
        )}
      </div>
    </div>
  );
}

function BiggestStreakPanel({
  data,
  loading,
}: {
  data: StreakData | null;
  loading: boolean;
}) {
  return (
    <div className="flex flex-col items-center justify-center" style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel className="text-subtle text-center">MAX TROPHY</SectionLabel>
      {loading ? (
        <div className="mt-1 flex justify-center">
          <span className="block h-5 w-12 bg-surface2" />
        </div>
      ) : data ? (
        <>
          <span className="flex items-center gap-1.5 my-0.5">
            <Trophy size={14} color="#ffc63a" />
            <span className="font-display text-[18px] leading-none tracking-[0.04em]">
              ×{data.count}
            </span>
          </span>
          <SectionLabel className="text-subtle text-center">STREAK</SectionLabel>
        </>
      ) : (
        <div className="mono text-[12px] text-muted text-center mt-1">—</div>
      )}
    </div>
  );
}

function MobileExpandedRow({
  row,
  to,
  activeFormat,
  activeColors,
  otherCombos,
}: {
  row: LeaderboardTableRow;
  to: PlayerLinkTo;
  activeFormat: string;
  activeColors: string;
  otherCombos: string[];
}) {
  const { events } = useDelayedExpandedData(row.slug, row.setCode);
  // events are DESC-sorted by finishedAt — first matching trophy is the most recent
  const lastTrophy = useMemo(() => {
    if (!events) return null;
    const filtersActive = activeFormat !== "ALL" || activeColors !== "ALL";
    if (!filtersActive) {
      for (const e of events) if (e.isTrophy) return e;
      return null;
    }
    return filterTrophyEvents(events, activeFormat, activeColors, otherCombos)[0] ?? null;
  }, [events, activeFormat, activeColors, otherCombos]);

  return (
    <Link
      to={to}
      aria-label={`View ${row.displayName}'s profile`}
      className="pt-2 pb-3 pr-3.5 pl-9 flex items-center gap-3 border-t border-dashed border-border2 cursor-pointer transition-colors hover:bg-green/5 no-underline text-inherit"
    >
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <span className="font-display text-[12px] tracking-[0.12em] text-muted tabular-nums">
          {row.events} EVENTS · <Record wins={row.wins} losses={row.losses} /> · {winPct(row.wins, row.losses)}%
        </span>
        <div className="flex items-center gap-1.5 min-h-[14px]">
          {!events ? (
            <span className="block h-3 w-40 bg-surface2" />
          ) : lastTrophy ? (
            <>
              <SectionLabel size={11} letterSpacing="0.18em">LAST TROPHY</SectionLabel>
              <Trophy size={12} color="#ffc63a" />
              <Pips colors={lastTrophy.colors} size={12} />
              <span className="text-dim text-[11px]">·</span>
              <span className="font-display text-[11px] tracking-[0.08em] text-muted">
                {prettyFormat(lastTrophy.format).toUpperCase()}
              </span>
              <span className="text-dim text-[11px]">·</span>
              <span className="font-display text-[11px] tracking-[0.08em] text-dim tabular-nums">{relativeTime(lastTrophy.finishedAt)}</span>
            </>
          ) : null}
        </div>
      </div>
      <span className="font-display text-[12px] leading-none tracking-[0.18em] text-green inline-flex items-center gap-1.5 shrink-0">
        VIEW PROFILE
        <ArrowRight size={12} />
      </span>
    </Link>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function goToSet(
  navigate: ReturnType<typeof useNavigate>,
  code: string,
  sets: SetSummary[] | undefined,
  searchParams: URLSearchParams,
) {
  const activeCode = sets?.find((s) => s.isActive)?.code;
  navigate({
    pathname: code === activeCode ? "/" : `/${code}`,
    search: searchParams.toString(),
  });
}
