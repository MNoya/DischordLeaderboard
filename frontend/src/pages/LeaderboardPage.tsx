import { useNavigate, useParams } from "react-router-dom";
import { useMemo, useState } from "react";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { SetGlyph } from "../components/Brand";
import { Pips } from "../components/ManaPips";
import { SetSwitcherDesktop, SetSwitcherMobile } from "../components/SetSwitcher";
import { FilterDropdown } from "../components/FilterDropdown";
import { LeaderboardSidebar } from "../components/LeaderboardSidebar";
import { LeaderboardTable } from "../components/LeaderboardTable";
import { SectionLabel } from "../components/SectionLabel";
import { ChamferedButton } from "../components/ChamferedButton";
import { Record } from "../components/Record";
import { DonutChart } from "../components/DonutChart";
import { TrophyCount } from "../components/TrophyCount";

import {
  applyFormatFilter,
  useArchetypeLeaderboard,
  useDraftEvents,
  useIdlePrefetchOtherSets,
  useLeaderboard,
  usePlayerProfile,
  useSets,
} from "../data/hooks";
import { fmtRange, lastUpdated, mainColors, sumEvents, weekOfSet, winPct } from "../data/utils";
import { ARCHETYPE_OPTIONS, FORMAT_OPTIONS } from "../data/filters";
import type { LeaderboardRow, PlayerDraftEvent, PlayerFormatBreakdown, SetSummary } from "../types/leaderboard";
import type { LeaderboardTableRow } from "../components/LeaderboardTable";

// Per-format swatch colors — must match the real backend `format_label` keys
// (Premier / Trad / Quick / Sealed / Trad Sealed / Arena Direct / LCQ). Falls
// back to a neutral blue for any unknown format.
const FMT_COLORS: Record<string, string> = {
  Premier: "#2ee85c",
  Trad: "#22d4c0",
  Quick: "#ffc63a",
  Sealed: "#e85cd2",
  "Trad Sealed": "#ff7d5c",
  "Arena Direct": "#9c7ce8",
  LCQ: "#5c8aff",
};

const FMT_DEFAULT_COLOR = "#5c8aff";

// ─── Page entry ────────────────────────────────────────────────────────────

export function LeaderboardPage() {
  const params = useParams<{ setCode?: string }>();
  const isMobile = useIsMobile();
  const { data: sets } = useSets();
  const activeSet = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const setMeta = sets?.find((s) => s.code === activeSet);

  const [format, setFormat] = useState("ALL");
  const [archetype, setArchetype] = useState("ALL");
  const archetypeMode = archetype !== "ALL";

  // Two data sources, selected at runtime: the main public_leaderboard for the
  // ALL view, and public_archetype_leaderboard (subset-replay scoring) when an
  // archetype is selected. Both hooks fire only when their query is enabled.
  const lb = useLeaderboard(archetypeMode ? undefined : activeSet);
  const arch = useArchetypeLeaderboard(
    archetypeMode ? activeSet : undefined,
    archetypeMode ? archetype : undefined,
  );

  const rows: LeaderboardTableRow[] | undefined = archetypeMode ? arch.data : lb.data;
  const isLoading = archetypeMode ? arch.isLoading : lb.isLoading;
  const error = (archetypeMode ? arch.error : lb.error) as Error | null;

  useIdlePrefetchOtherSets(activeSet, sets);

  // Archetype leaderboard ignores the format filter (per spec out-of-scope:
  // archetype × format is deferred). For the main board, format applies.
  const filtered = useMemo(
    () => (archetypeMode ? rows : applyFormatFilter(rows as LeaderboardRow[] | undefined, format)),
    [rows, format, archetypeMode],
  );

  const filterProps: FilterRowProps = { format, setFormat, archetype, setArchetype };

  return isMobile ? (
    <Mobile
      activeSet={activeSet}
      sets={sets}
      rows={filtered}
      isLoading={isLoading}
      error={error}
      filters={filterProps}
      archetypeMode={archetypeMode}
    />
  ) : (
    <Desktop
      activeSet={activeSet}
      sets={sets}
      setMeta={setMeta}
      rows={filtered}
      isLoading={isLoading}
      error={error}
      filters={filterProps}
      archetypeMode={archetypeMode}
    />
  );
}

interface FilterRowProps {
  format: string;
  setFormat: (v: string) => void;
  archetype: string;
  setArchetype: (v: string) => void;
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
  archetypeMode,
}: {
  activeSet: string;
  sets: SetSummary[] | undefined;
  setMeta: SetSummary | undefined;
  rows: LeaderboardTableRow[] | undefined;
  isLoading: boolean;
  error: Error | null;
  filters: FilterRowProps;
  archetypeMode: boolean;
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen">
      <AppHeader subtitle="LEADERBOARD" />
      <SetHero activeSet={activeSet} setMeta={setMeta} sets={sets} onSelectSet={(c) => goToSet(navigate, c, sets)} />
      <FilterRow {...filters} rows={rows} />

      <div className="px-10 pb-10 grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
        <LeaderboardTable
          rows={rows}
          variant="desktop"
          loading={isLoading}
          error={error}
          renderExpanded={(r) => (
            <DesktopExpandedRow
              row={r}
              onView={() => navigate(`/${activeSet}/player/${r.slug}`)}
            />
          )}
        />
        <LeaderboardSidebar setCode={activeSet} />
      </div>
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
  archetype,
  setArchetype,
  rows,
}: FilterRowProps & { rows: LeaderboardTableRow[] | undefined }) {
  return (
    <div className="px-10 py-3.5 border-b border-border flex gap-3 items-center">
      <FilterDropdown label="FORMAT" value={format} options={FORMAT_OPTIONS} onChange={setFormat} />
      <FilterDropdown label="ARCHETYPE" value={archetype} options={ARCHETYPE_OPTIONS} onChange={setArchetype} />
      <span className="flex-1" />
      <div className="mono text-[10px] text-muted">
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
  archetypeMode: _archetypeMode,
}: {
  activeSet: string;
  sets: SetSummary[] | undefined;
  rows: LeaderboardTableRow[] | undefined;
  isLoading: boolean;
  error: Error | null;
  filters: FilterRowProps;
  archetypeMode: boolean;
}) {
  const navigate = useNavigate();
  return (
    <div className="bg-bg text-text min-h-screen">
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

        <div className="px-4 py-1.5 flex items-center gap-1.5 border-b border-border bg-bg">
          <FilterDropdown
            label="FORMAT"
            value={filters.format}
            options={FORMAT_OPTIONS}
            onChange={filters.setFormat}
            variant="mobile"
          />
          <FilterDropdown
            label="ARCHETYPE"
            value={filters.archetype}
            options={ARCHETYPE_OPTIONS}
            onChange={filters.setArchetype}
            variant="mobile"
          />
        </div>
      </div>

      <LeaderboardTable
        rows={rows}
        variant="mobile"
        loading={isLoading}
        error={error}
        renderExpanded={(r) => (
          <MobileExpandedRow row={r} onView={() => navigate(`/${activeSet}/player/${r.slug}`)} />
        )}
      />
    </div>
  );
}

// ─── Expanded rows ─────────────────────────────────────────────────────────

function DesktopExpandedRow({ row, onView }: { row: LeaderboardTableRow; onView: () => void }) {
  // Lazy fetch — these only fire when the row is expanded since
  // LeaderboardTable conditionally mounts this component. Cache survives
  // re-collapses and pre-warms the player profile route.
  const { data: profile } = usePlayerProfile(row.slug, row.setCode);
  const { data: events } = useDraftEvents(row.slug, row.setCode);

  return (
    <div
      className="pt-3.5 pb-[18px] pr-4 pl-[76px] border-t border-dashed border-border2 grid items-center gap-6"
      style={{ gridTemplateColumns: "1.2fr 1fr auto" }}
    >
      <FormatBreakdownPreview breakdown={profile?.formatBreakdown} totalScore={row.score} />
      <MostPlayedDecks events={events} />
      <div onClick={(e) => e.stopPropagation()} className="self-center">
        <ChamferedButton onClick={onView}>VIEW PROFILE →</ChamferedButton>
      </div>
    </div>
  );
}

function FormatBreakdownPreview({
  breakdown,
  totalScore,
}: {
  breakdown: PlayerFormatBreakdown[] | undefined;
  totalScore: number;
}) {
  const ready = breakdown && breakdown.length > 0;
  const total = ready ? Math.max(1, breakdown.reduce((s, f) => s + f.scoreContribution, 0)) : 1;
  return (
    <div>
      <SectionLabel>FORMAT BREAKDOWN</SectionLabel>
      <div className="flex items-center gap-3.5 mt-2">
        <DonutChart
          entries={(ready ? breakdown : []).map((f) => ({
            key: f.formatLabel,
            value: f.scoreContribution / total,
            color: FMT_COLORS[f.formatLabel] ?? FMT_DEFAULT_COLOR,
          }))}
          radius={28}
          strokeWidth={10}
          size={76}
        />
        <div className="flex-1 flex flex-col gap-0.5">
          {ready ? (
            breakdown.map((f) => {
              const color = FMT_COLORS[f.formatLabel] ?? FMT_DEFAULT_COLOR;
              return (
                <div
                  key={f.formatLabel}
                  className="grid gap-2 items-center"
                  style={{ gridTemplateColumns: "10px 1fr auto" }}
                >
                  <span className="w-2 h-2" style={{ background: color }} />
                  <span className="font-display text-[11px] tracking-[0.1em]">
                    {f.formatLabel.toUpperCase()}
                  </span>
                  <span className="mono text-[11px] text-muted">
                    {Math.round(f.scoreContribution)}
                  </span>
                </div>
              );
            })
          ) : (
            <span className="mono text-[11px] text-muted" style={{ minHeight: 76 }}>
              LOADING…
            </span>
          )}
          {/* Reserve room for the score total even while loading */}
          {!ready && <span className="mono text-[11px] text-dim">{Math.round(totalScore)}</span>}
        </div>
      </div>
    </div>
  );
}

function MostPlayedDecks({ events }: { events: PlayerDraftEvent[] | undefined }) {
  // Aggregate top archetypes by event count from real events. Trophies are
  // tallied from `isTrophy` so the icon next to each row reflects actual runs,
  // not a synthetic estimate.
  const top = useMemo(() => {
    if (!events || events.length === 0) return [];
    const count: Record<string, number> = {};
    const trophies: Record<string, number> = {};
    for (const e of events) {
      const main = mainColors(e.colors);
      if (main.length < 2) continue;
      const arch = main.slice(0, 2);
      count[arch] = (count[arch] ?? 0) + 1;
      if (e.isTrophy) trophies[arch] = (trophies[arch] ?? 0) + 1;
    }
    return Object.entries(count)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([code, n]) => ({ code, count: n, trophies: trophies[code] ?? 0 }));
  }, [events]);

  return (
    <div>
      <SectionLabel>MOST PLAYED DECKS</SectionLabel>
      <div className="flex flex-col gap-1 mt-2">
        {top.length === 0 ? (
          <span className="mono text-[11px] text-muted">LOADING…</span>
        ) : (
          top.map((d) => (
            <div
              key={d.code}
              className="grid gap-2 items-center"
              style={{ gridTemplateColumns: "auto 40px 1fr auto" }}
            >
              <Pips colors={d.code} size={11} />
              <span className="font-display text-[13px] tracking-[0.06em]">{d.code}</span>
              <TrophyCount count={d.trophies} size="compact" className="text-muted" />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function MobileExpandedRow({ row, onView }: { row: LeaderboardTableRow; onView: () => void }) {
  return (
    <div className="pt-1 pb-3 pr-3.5 pl-9 flex flex-col gap-2 border-t border-dashed border-border2">
      <div className="flex items-center justify-between gap-2 mt-2">
        <span className="mono text-[10px] text-muted">
          {row.events} EVENTS · <Record wins={row.wins} losses={row.losses} /> · {winPct(row.wins, row.losses)}%
        </span>
        <div onClick={(e) => e.stopPropagation()}>
          <ChamferedButton size="sm" onClick={onView}>
            VIEW PROFILE →
          </ChamferedButton>
        </div>
      </div>
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function goToSet(navigate: ReturnType<typeof useNavigate>, code: string, sets: SetSummary[] | undefined) {
  const activeCode = sets?.find((s) => s.isActive)?.code;
  navigate(code === activeCode ? "/" : `/${code}`);
}
