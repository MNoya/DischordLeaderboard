import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Fragment, useEffect, useMemo, useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { ArrowRight, SetGlyph, Trophy } from "../components/Brand";
import { Footer } from "../components/Footer";
import { Pips } from "../components/ManaPips";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { FilterDropdown } from "../components/FilterDropdown";
import { ColorsSwitcher } from "../components/ColorsSwitcher";
import { LeaderboardSidebar } from "../components/LeaderboardSidebar";
import { LeaderboardColumnHeader, LeaderboardTable } from "../components/LeaderboardTable";
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
import { colorsOf, fmtRange, lastUpdated, prettyFormat, relativeTime, sumEvents, weekOfSet, winPct } from "../data/utils";
import { colorsDisplayName, FORMAT_OPTIONS, MULTI, OTHER } from "../data/filters";
import { FMT_COLORS, FMT_DEFAULT_COLOR, renderFormatOption, shortFormat } from "../data/format-display";
import type { LeaderboardRow, PlayerDraftEvent, PlayerFormatBreakdown, SetSummary } from "../types/leaderboard";
import type { LeaderboardTableRow } from "../components/LeaderboardTable";

// ─── Page entry ────────────────────────────────────────────────────────────

export function LeaderboardPage() {
  const params = useParams<{ setCode?: string }>();
  const isMobile = useIsMobile();
  const { data: sets } = useSets();
  const activeSet = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const setMeta = sets?.find((s) => s.code === activeSet);

  // Filters live in the URL as query params (?format=Premier or ?colors=WR).
  // Per spec they're mutually exclusive, so picking a non-ALL value in one
  // clears the other.
  const [searchParams, setSearchParams] = useSearchParams();
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
  const rows: LeaderboardTableRow[] | undefined = active.data;
  const isLoading = active.isLoading;
  const error = active.error as Error | null;

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
    />
  );
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
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col">
      <AppHeader subtitle="LEADERBOARD" />
      <SetHero activeSet={activeSet} setMeta={setMeta} sets={sets} onSelectSet={(c) => goToSet(navigate, c, sets)} />
      <FilterRow {...filters} rows={rows} />

      <div className="px-10 grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
        <LeaderboardTable
          rows={rows}
          variant="desktop"
          loading={isLoading}
          error={error}
          renderExpanded={(r) => (
            <DesktopExpandedRow
              row={r}
              to={`/${activeSet}/player/${r.slug}`}
            />
          )}
        />
        <div className="pt-4">
          <LeaderboardSidebar setCode={activeSet} colors={filters.colors} otherCombos={otherCombos} />
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
}: {
  activeSet: string;
  setMeta: SetSummary | undefined;
  sets: SetSummary[] | undefined;
  onSelectSet: (code: string) => void;
}) {
  const week = weekOfSet(setMeta);
  return (
    <div className="px-10 py-5 border-b border-border bg-surface flex items-center gap-6">
      <SetGlyph code={activeSet} size={84} />
      <div>
        <SectionLabel size={13}>CURRENT SET</SectionLabel>
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
}: {
  activeSet: string;
  sets: SetSummary[] | undefined;
  rows: LeaderboardTableRow[] | undefined;
  isLoading: boolean;
  error: Error | null;
  filters: FilterRowProps;
  colorsMode: boolean;
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen flex flex-col">
      <div className="sticky top-0 z-10 bg-bg">
        <AppHeader subtitle="LEADERBOARD" />

        <div className="px-4 py-2 border-b border-border bg-surface">
          {sets && (
            <SetSwitcherMobile
              sets={sets}
              activeCode={activeSet}
              onChange={(code) => goToSet(navigate, code, sets)}
            />
          )}
        </div>

        <div className="px-4 py-1.5 border-b border-border bg-bg">
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
        <LeaderboardColumnHeader variant="mobile" />
      </div>

      <LeaderboardTable
        rows={rows}
        variant="mobile"
        loading={isLoading}
        error={error}
        showHeader={false}
        renderExpanded={(r) => (
          <MobileExpandedRow row={r} to={`/${activeSet}/player/${r.slug}`} />
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

function DesktopExpandedRow({ row, to }: { row: LeaderboardTableRow; to: string }) {
  const { profile, events } = useDelayedExpandedData(row.slug, row.setCode);
  const { lastTrophies, biggestStreak } = useHighlights(events);

  return (
    <Link
      to={to}
      aria-label={`View ${row.displayName}'s profile`}
      className="pt-3.5 pb-4 pr-4 pl-[76px] border-t border-dashed border-border2 flex items-center gap-6 cursor-pointer transition-colors hover:bg-green/5 no-underline text-inherit"
    >
      <div className="flex-1 min-w-0"><FormatBreakdownPreview breakdown={profile?.formatBreakdown} /></div>
      <div className="flex-1 min-w-0"><MostPlayedDecks events={events} /></div>
      <div className="flex-1 min-w-0"><LastTrophyPanel data={lastTrophies} loading={!events} /></div>
      <div className="flex-1 min-w-0"><BiggestStreakPanel data={biggestStreak} loading={!events} /></div>
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
  return (
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel>FORMAT BREAKDOWN</SectionLabel>
      <div className="flex items-center gap-3.5 mt-2">
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
        <div
          className="grid items-center gap-x-3 gap-y-0.5"
          style={{ gridTemplateColumns: "auto auto auto" }}
        >
          {ready
            ? sorted.map((f) => {
                const color = FMT_COLORS[f.formatLabel] ?? FMT_DEFAULT_COLOR;
                return (
                  <Fragment key={f.formatLabel}>
                    <span className="w-2 h-2 shrink-0" style={{ background: color }} />
                    <span className="font-display text-[11px] tracking-[0.1em]">
                      {f.formatLabel.toUpperCase()}
                    </span>
                    <span className="mono text-[11px] text-muted tabular-nums justify-self-end">
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
      <SectionLabel>MOST PLAYED DECKS</SectionLabel>
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
}: {
  data: PlayerDraftEvent[];
  loading: boolean;
}) {
  return (
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel>LAST TROPHIES</SectionLabel>
      <div
        className="grid items-center gap-x-3 gap-y-1 mt-2.5 w-fit"
        style={{ gridTemplateColumns: "auto 108px 50px auto" }}
      >
        {loading ? (
          [0, 1, 2].map((i) => (
            <Fragment key={i}>
              <span className="w-[26px] h-3 bg-surface2 shrink-0" />
              <span className="h-3 bg-surface2" style={{ width: 50 }} />
              <span className="h-3 bg-surface2" style={{ width: 36 }} />
              <span className="h-3 bg-surface2" style={{ width: 24 }} />
            </Fragment>
          ))
        ) : data.length > 0 ? (
          data.map((e) => (
            <Fragment key={e.eventId}>
              <Pips colors={e.colors} size={11} />
              <span className="font-display text-[13px] tracking-[0.06em] text-muted">
                {shortFormat(e.format)}
              </span>
              <Record
                wins={e.wins}
                losses={e.losses}
                mono
                className="mono text-[12px] text-muted"
              />
              <span className="mono text-[12px] text-dim">{relativeTime(e.finishedAt)}</span>
            </Fragment>
          ))
        ) : (
          <div className="mono text-[12px] text-muted col-span-4">NONE YET</div>
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
    <div style={{ minHeight: PANEL_MIN_HEIGHT }}>
      <SectionLabel>BIGGEST TROPHY STREAK</SectionLabel>
      <div className="mt-2.5">
        {loading ? (
          <span className="block h-5 w-24 bg-surface2" />
        ) : data ? (
          <div className="flex items-center gap-2">
            <Trophy size={14} color="#ffc63a" />
            <span className="font-display text-[18px] leading-none tracking-[0.04em]">
              ×{data.count}
            </span>
            <span className="text-dim text-[12px]">·</span>
            <span className="font-display text-[13px] tracking-[0.06em] text-muted">
              {prettyFormat(data.format).toUpperCase()}
            </span>
          </div>
        ) : (
          <div className="mono text-[12px] text-muted">—</div>
        )}
      </div>
    </div>
  );
}

function MobileExpandedRow({ row, to }: { row: LeaderboardTableRow; to: string }) {
  const { events } = useDelayedExpandedData(row.slug, row.setCode);
  // events are DESC-sorted by finishedAt — first hit is the most recent trophy
  const lastTrophy = useMemo(() => {
    if (!events) return null;
    for (const e of events) if (e.isTrophy) return e;
    return null;
  }, [events]);

  return (
    <Link
      to={to}
      aria-label={`View ${row.displayName}'s profile`}
      className="pt-2 pb-3 pr-3.5 pl-9 flex items-center gap-3 border-t border-dashed border-border2 cursor-pointer transition-colors hover:bg-green/5 no-underline text-inherit"
    >
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        <span className="mono text-[10px] text-muted">
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
              <span className="mono text-[11px] text-dim">{relativeTime(lastTrophy.finishedAt)}</span>
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

function goToSet(navigate: ReturnType<typeof useNavigate>, code: string, sets: SetSummary[] | undefined) {
  const activeCode = sets?.find((s) => s.isActive)?.code;
  navigate(code === activeCode ? "/" : `/${code}`);
}
