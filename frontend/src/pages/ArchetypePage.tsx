import { useNavigate, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { Trophy } from "../components/Brand";
import { Pip, Pips } from "../components/ManaPips";
import { SectionLabel } from "../components/SectionLabel";
import { ChamferedButton } from "../components/ChamferedButton";
import { Record } from "../components/Record";
import { LeaderboardTable } from "../components/LeaderboardTable";

import { useMemo } from "react";
import {
  useArchetypeLeaderboard,
  useDraftEvents,
  useRecentTrophies,
  useSets,
} from "../data/hooks";
import { archetypeOf, relativeTime, winPct } from "../data/utils";
import {
  ARCHETYPE_NAMES,
  MONO_ARCHETYPES,
  TWO_COLOR_ARCHETYPES,
} from "../data/filters";
import { cn } from "../lib/utils";
import { SurfaceCard } from "../components/SurfaceCard";
import type {
  ArchetypeLeaderboardRow,
  SetSummary,
} from "../types/leaderboard";

// ─── Page entry ────────────────────────────────────────────────────────────

export function ArchetypePage() {
  const params = useParams<{ setCode?: string; archetype?: string }>();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { data: sets } = useSets();
  const setCode = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const archetype = params.archetype ?? "WR";
  const { data: rows, isLoading, error } = useArchetypeLeaderboard(setCode, archetype);

  const goTo = (a: string) =>
    navigate(setCode === sets?.find((s) => s.isActive)?.code ? `/archetypes/${a}` : `/${setCode}/archetypes/${a}`);

  return isMobile ? (
    <Mobile
      setCode={setCode}
      archetype={archetype}
      rows={rows}
      isLoading={isLoading}
      error={error as Error | null}
      goTo={goTo}
      navigate={navigate}
    />
  ) : (
    <Desktop
      setCode={setCode}
      archetype={archetype}
      rows={rows}
      isLoading={isLoading}
      error={error as Error | null}
      goTo={goTo}
      navigate={navigate}
      sets={sets}
    />
  );
}

interface SubpageProps {
  setCode: string;
  archetype: string;
  rows: ArchetypeLeaderboardRow[] | undefined;
  isLoading: boolean;
  error: Error | null;
  goTo: (a: string) => void;
  navigate: ReturnType<typeof useNavigate>;
}

// ─── Desktop ───────────────────────────────────────────────────────────────

function Desktop({
  setCode,
  archetype,
  rows,
  isLoading,
  error,
  goTo,
  navigate,
}: SubpageProps & { sets: SetSummary[] | undefined }) {
  return (
    <div className="bg-bg text-text min-h-screen">
      <AppHeader subtitle="ARCHETYPE" />
      <Hero setCode={setCode} archetype={archetype} rows={rows} />
      <ArchetypeSwitcher activeCode={archetype} onChange={goTo} variant="desktop" />

      <div className="px-10 pb-10 grid gap-6" style={{ gridTemplateColumns: "1fr 280px" }}>
        <LeaderboardTable
          rows={rows}
          variant="desktop"
          loading={isLoading}
          error={error}
          renderExpanded={(r) => (
            <DesktopExpandedRow
              slug={r.slug}
              setCode={setCode}
              archetype={archetype}
              onView={() => navigate(`/${setCode}/player/${r.slug}`)}
            />
          )}
        />
        <ArchetypeSidebar setCode={setCode} archetype={archetype} />
      </div>
    </div>
  );
}

// ─── Mobile ────────────────────────────────────────────────────────────────

function Mobile({
  setCode,
  archetype,
  rows,
  isLoading,
  error,
  goTo,
  navigate,
}: SubpageProps) {
  return (
    <div className="bg-bg text-text min-h-screen">
      <div className="sticky top-0 z-10 bg-bg">
        <AppHeader subtitle="ARCHETYPE" />
        <Hero setCode={setCode} archetype={archetype} rows={rows} compact />
        <ArchetypeSwitcher activeCode={archetype} onChange={goTo} variant="mobile" />
      </div>

      <LeaderboardTable
        rows={rows}
        variant="mobile"
        loading={isLoading}
        error={error}
        renderExpanded={(r) => (
          <MobileExpandedRow row={r} onView={() => navigate(`/${setCode}/player/${r.slug}`)} />
        )}
      />
    </div>
  );
}

// ─── Hero ──────────────────────────────────────────────────────────────────

function Hero({
  setCode,
  archetype,
  rows,
  compact = false,
}: {
  setCode: string;
  archetype: string;
  rows: ArchetypeLeaderboardRow[] | undefined;
  compact?: boolean;
}) {
  return (
    <div
      className={cn(
        "border-b border-border bg-surface flex gap-8",
        compact ? "px-[18px] py-4 flex-col items-start" : "px-10 py-7 items-center",
      )}
    >
      <div>
        <SectionLabel size={12} letterSpacing="0.25em">
          {setCode} · ARCHETYPE BOARD
        </SectionLabel>
        <div className="flex items-center gap-[18px] mt-1 flex-wrap">
          <h1
            className={cn(
              "font-display tracking-[0.04em] m-0 leading-none text-green",
              compact ? "text-[44px]" : "text-[70px]",
            )}
          >
            {ARCHETYPE_NAMES[archetype] ?? archetype}
          </h1>
          <div className="flex gap-1.5 items-center py-1.5 px-2.5 border border-border2 bg-bg">
            {[...archetype].map((c) => (
              <Pip key={c} c={c as "W" | "U" | "B" | "R" | "G"} size={compact ? 24 : 36} />
            ))}
          </div>
        </div>
        <div className="mono text-[11px] text-muted mt-2">
          “IF {archetype} WERE YOUR ONLY DECK.” · {rows?.reduce((s, r) => s + r.events, 0) ?? 0} EVENTS · {rows?.length ?? 0} PLAYERS · SUBSET-REPLAY POINTS
        </div>
      </div>
    </div>
  );
}

// ─── Archetype switcher ────────────────────────────────────────────────────

function ArchetypeSwitcher({
  activeCode,
  onChange,
  variant,
}: {
  activeCode: string;
  onChange: (code: string) => void;
  variant: "desktop" | "mobile";
}) {
  if (variant === "mobile") {
    return (
      <div className="py-2 px-3 border-b border-border flex gap-1 overflow-x-auto bg-bg no-scrollbar">
        {TWO_COLOR_ARCHETYPES.map((code) => (
          <SwitcherChip key={code} code={code} active={code === activeCode} onClick={() => onChange(code)} pipSize={12} />
        ))}
      </div>
    );
  }
  return (
    <div className="py-2 px-10 pb-3.5 flex gap-2 items-center flex-wrap border-b border-border">
      <SectionLabel>SWITCH ARCHETYPE</SectionLabel>
      <span className="flex-1" />
      <div className="flex gap-1 flex-wrap justify-end">
        {[...MONO_ARCHETYPES, ...TWO_COLOR_ARCHETYPES].map((code) => (
          <SwitcherChip key={code} code={code} active={code === activeCode} onClick={() => onChange(code)} pipSize={11} />
        ))}
      </div>
    </div>
  );
}

function SwitcherChip({
  code,
  active,
  onClick,
  pipSize,
}: {
  code: string;
  active: boolean;
  onClick: () => void;
  pipSize: number;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "shrink-0 py-[5px] px-[7px] border inline-flex gap-0.5 cursor-pointer transition-colors",
        active ? "border-green bg-green/10" : "border-border2 bg-transparent hover:bg-surface",
      )}
      aria-label={code}
    >
      {[...code].map((c) => (
        <Pip key={c} c={c as "W" | "U" | "B" | "R" | "G"} size={pipSize} />
      ))}
    </button>
  );
}

// ─── Expanded rows ─────────────────────────────────────────────────────────

function DesktopExpandedRow({
  slug,
  setCode,
  archetype,
  onView,
}: {
  slug: string;
  setCode: string;
  archetype: string;
  onView: () => void;
}) {
  // Lazy fetch — fires when this row expands. Filter to events whose
  // WUBRG-normalized main colors equal the current archetype, take the most
  // recent 6.
  const { data: events } = useDraftEvents(slug, setCode);
  const recent = useMemo(() => {
    if (!events) return [];
    return events
      .filter((e) => archetypeOf(e.colors) === archetype)
      .slice(0, 6);
  }, [events, archetype]);

  return (
    <div className="pt-3.5 pb-[18px] pr-4 pl-[76px] border-t border-dashed border-border2 flex gap-7 items-center">
      <div className="flex-1">
        <SectionLabel>RECENT {archetype} DRAFTS</SectionLabel>
        <div className="flex gap-1.5 mt-2 flex-wrap">
          {events == null ? (
            <span className="mono text-[11px] text-muted">LOADING…</span>
          ) : recent.length === 0 ? (
            <span className="mono text-[11px] text-muted">NO {archetype} DRAFTS RECORDED</span>
          ) : (
            recent.map((e) => (
              <span
                key={e.eventId}
                className="inline-flex items-center gap-1 py-[3px] px-2 border border-border2 font-mono text-[11px]"
              >
                {e.isTrophy && <Trophy size={10} color="#ffc63a" />}
                <Record
                  wins={e.wins}
                  losses={e.losses}
                  mono
                  color={e.wins >= 4 ? "#2ee85c" : "#e6ecf5"}
                />
              </span>
            ))
          )}
        </div>
      </div>
      <div onClick={(e) => e.stopPropagation()} className="self-center">
        <ChamferedButton onClick={onView}>VIEW PROFILE →</ChamferedButton>
      </div>
    </div>
  );
}

function MobileExpandedRow({ row, onView }: { row: ArchetypeLeaderboardRow; onView: () => void }) {
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

// ─── Sidebar ───────────────────────────────────────────────────────────────

function ArchetypeSidebar({
  setCode,
  archetype,
}: {
  setCode: string;
  archetype: string;
}) {
  // Pull the global recent-trophies feed and filter to events in this archetype.
  // Once the backend has an archetype-filterable view we can push the predicate
  // server-side; for now the feed is small enough that client-side is fine.
  const { data: recent } = useRecentTrophies(setCode, 30);
  const archetypeTrophies = (recent ?? []).filter(
    (t) => archetypeOf(t.colors) === archetype,
  ).slice(0, 8);

  return (
    <aside className="flex flex-col gap-4 pt-6">
      <SurfaceCard>
        <div className="flex items-center gap-1.5 mb-1">
          <Pips colors={archetype} size={11} />
          <SectionLabel>RECENT {archetype} TROPHIES</SectionLabel>
        </div>
        <div className="mono text-[10px] text-dim mb-2.5">{setCode}</div>
        {!recent ? (
          <div className="mono text-[11px] text-muted py-2">LOADING…</div>
        ) : archetypeTrophies.length === 0 ? (
          <div className="mono text-[11px] text-muted py-2">
            NO {archetype} TROPHIES YET
          </div>
        ) : (
          archetypeTrophies.map((t, i) => (
            <div
              key={`${t.slug}-${t.finishedAt}`}
              className={cn(
                "grid gap-2 items-center py-[7px]",
                i && "border-t border-border",
              )}
              style={{ gridTemplateColumns: "auto 1fr auto auto" }}
            >
              <Trophy size={14} color="#ffc63a" />
              <span className="font-display text-[13px] tracking-[0.04em] whitespace-nowrap overflow-hidden text-ellipsis">
                {t.displayName.toUpperCase()}
              </span>
              <span className="mono text-[10px] text-muted">
                {t.wins}–{t.losses}
              </span>
              <span className="mono text-[10px] text-dim">{relativeTime(t.finishedAt)}</span>
            </div>
          ))
        )}
      </SurfaceCard>
    </aside>
  );
}
