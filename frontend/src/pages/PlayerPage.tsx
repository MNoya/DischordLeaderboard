import React, { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { useIsMobile } from "../lib/use-is-mobile";
import { AAvatar, SetGlyph, Trophy, fmtPts } from "../components/Brand";
import { Pips } from "../components/ManaPips";
import { StatChip } from "../components/StatChip";
import { FilterDropdown } from "../components/FilterDropdown";
import { SectionLabel } from "../components/SectionLabel";
import { Record } from "../components/Record";
import { DonutChart } from "../components/DonutChart";
import { ErrorState } from "../components/ErrorState";
import { TrophyCount } from "../components/TrophyCount";

import { useDraftEvents, usePlayerProfile, useSets } from "../data/hooks";
import { archetypeOf, mainColors, winPct } from "../data/utils";
import { ARCHETYPE_OPTIONS_LONG, FORMAT_OPTIONS_LONG } from "../data/filters";
import { cn } from "../lib/utils";
import type {
  PlayerDraftEvent,
  PlayerFormatBreakdown,
  PlayerProfile,
} from "../types/leaderboard";

// ─── Color palettes ────────────────────────────────────────────────────────

const FMT_COLORS: Record<string, string> = {
  Premier: "#2ee85c",
  Trad: "#22d4c0",
  Quick: "#ffc63a",
  Sealed: "#e85cd2",
  "Trad Sealed": "#ff7d5c",
  LCQ: "#5c8aff",
};

const ARCH_PALETTE = [
  "#2ee85c", "#22d4c0", "#ffc63a", "#e85cd2",
  "#5c8aff", "#ff7d5c", "#ff5e5e", "#9c7ce8",
];

const COLOR_STROKES: Record<string, string> = {
  W: "#f0e6a8",
  U: "#6db3e8",
  B: "#7a7472",
  R: "#ff5e5e",
  G: "#5fb56e",
};

const COLOR_KEYS: Array<"W" | "U" | "B" | "R" | "G"> = ["W", "U", "B", "R", "G"];

// ─── Page entry ────────────────────────────────────────────────────────────

export function PlayerPage() {
  const params = useParams<{ slug: string; setCode?: string }>();
  const slug = params.slug!;
  const { data: sets } = useSets();
  const setCode = params.setCode ?? sets?.find((s) => s.isActive)?.code ?? "SOS";
  const { data: profile, isLoading, error } = usePlayerProfile(slug, setCode);
  const { data: events } = useDraftEvents(slug, setCode);
  const isMobile = useIsMobile();

  if (error) {
    return (
      <div className="bg-bg text-text min-h-screen">
        <AppHeader subtitle="PLAYER" />
        <ErrorState error={error as Error} compact={isMobile} />
      </div>
    );
  }

  if (isLoading || !profile) {
    return (
      <div className="bg-bg text-text min-h-screen">
        <AppHeader subtitle="PLAYER" />
        <div className="p-20 text-center text-muted font-display tracking-[0.2em]">
          {isLoading ? "LOADING…" : "PLAYER NOT FOUND"}
        </div>
      </div>
    );
  }

  return isMobile ? (
    <Mobile profile={profile} events={events ?? []} />
  ) : (
    <Desktop profile={profile} events={events ?? []} />
  );
}

// ─── Aggregation ───────────────────────────────────────────────────────────

interface PlayerAggregates {
  colorCount: Record<"W" | "U" | "B" | "R" | "G", number>;
  archCount: Record<string, number>;
  archTrophies: Record<string, number>;
}

function aggregate(events: PlayerDraftEvent[]): PlayerAggregates {
  const colorCount: PlayerAggregates["colorCount"] = { W: 0, U: 0, B: 0, R: 0, G: 0 };
  const archCount: Record<string, number> = {};
  const archTrophies: Record<string, number> = {};
  for (const e of events) {
    const main = mainColors(e.colors);
    for (const c of main) {
      if (c in colorCount) colorCount[c as keyof typeof colorCount]++;
    }
    if (main.length >= 2) {
      const arch = main.slice(0, 2);
      archCount[arch] = (archCount[arch] ?? 0) + 1;
      if (e.isTrophy) archTrophies[arch] = (archTrophies[arch] ?? 0) + 1;
    }
  }
  return { colorCount, archCount, archTrophies };
}

// ─── Desktop ───────────────────────────────────────────────────────────────

function Desktop({ profile, events }: { profile: PlayerProfile; events: PlayerDraftEvent[] }) {
  const navigate = useNavigate();
  const wp = winPct(profile.wins, profile.losses);

  const [formatFilter, setFormatFilter] = useState("ALL");
  const [archFilter, setArchFilter] = useState("ALL");

  const filtered = useMemo(
    () =>
      events.filter((e) => {
        if (formatFilter !== "ALL" && !e.format.toLowerCase().includes(formatFilter.toLowerCase())) return false;
        if (archFilter !== "ALL" && archetypeOf(e.colors) !== archFilter) return false;
        return true;
      }),
    [events, formatFilter, archFilter]
  );

  const nameLen = profile.displayName.length;
  const nameFs = nameLen <= 8 ? 64 : nameLen <= 12 ? 52 : nameLen <= 18 ? 40 : 32;

  return (
    <div className="bg-bg text-text min-h-screen">
      <AppHeader subtitle="PLAYER" />

      <section
        className="px-10 pt-7 pb-[30px] border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <BackButton onClick={() => navigate(-1)} />
        <div className="flex items-center gap-7">
          <AAvatar displayName={profile.displayName} avatarUrl={profile.avatarUrl} size={120} green />
          <div className="flex-1 min-w-0">
            <SectionLabel size={12} letterSpacing="0.25em">PLAYER</SectionLabel>
            <h1
              className="font-display tracking-[0.03em] m-0 mt-0.5 break-words"
              style={{ fontSize: nameFs, lineHeight: 0.95 }}
            >
              {profile.displayName.toUpperCase()}
            </h1>
            <div className="mt-2 flex items-center gap-2.5 font-display tracking-[0.18em]">
              <SetGlyph code={profile.setCode} size={22} />
              <span className="text-[18px]">{profile.setCode}</span>
              <span className="text-[12px] text-dim">·</span>
              <span className="text-[16px]">#{profile.rank}</span>
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
          archFilter={archFilter}
          setArchFilter={setArchFilter}
        />
      </div>
    </div>
  );
}

function StatStrip({ profile, wp }: { profile: PlayerProfile; wp: string }) {
  const tiles: Array<{ label: string; value: React.ReactNode; accent?: boolean }> = [
    {
      label: "TROPHIES",
      value: (
        <span className="flex items-center gap-1.5">
          <Trophy size={26} color="#ffc63a" />
          <span className="font-display text-[44px] leading-none">{profile.trophies}</span>
        </span>
      ),
    },
    {
      label: "EVENTS",
      value: <span className="font-display text-[44px] leading-none">{profile.events}</span>,
    },
    {
      label: "RECORD",
      value: (
        <Record
          mono
          wins={profile.wins}
          losses={profile.losses}
          separatorMargin={4}
          className="mono text-[32px] leading-none"
        />
      ),
    },
    {
      label: "WIN %",
      value: (
        <span className="font-display text-[44px] leading-none">
          {wp}
          <span className="text-[22px] text-muted">%</span>
        </span>
      ),
    },
    {
      label: "POINTS",
      value: (
        <span className="font-display text-[44px] leading-none text-green">{fmtPts(profile.score)}</span>
      ),
      accent: true,
    },
  ];
  return (
    <div
      className="grid border border-border2 bg-bg self-stretch"
      style={{ flex: "0 0 720px", gridTemplateColumns: "1fr 1fr 1.3fr 1fr 0.9fr" }}
    >
      {tiles.map((t, i) => (
        <div
          key={t.label}
          className={cn(
            "py-3.5 px-3 flex flex-col justify-between items-center text-center gap-3",
            i < tiles.length - 1 && "border-r border-border2",
          )}
        >
          <SectionLabel>{t.label}</SectionLabel>
          {t.value}
        </div>
      ))}
    </div>
  );
}

function BreakdownPanel({ profile, events }: { profile: PlayerProfile; events: PlayerDraftEvent[] }) {
  const total = profile.formatBreakdown.reduce((s, f) => s + f.scoreContribution, 0) || 1;
  const { colorCount, archCount, archTrophies } = aggregate(events);
  const archEntries = Object.entries(archCount).sort((a, b) => b[1] - a[1]);
  const archTotal = archEntries.reduce((s, [, n]) => s + n, 0) || 1;
  const colorTotal = Object.values(colorCount).reduce((a, b) => a + b, 0) || 1;

  return (
    <section className="py-6 pl-10 pr-8 border-r border-border">
      <SectionLabel size={13} className="mb-3.5">POINTS BY FORMAT</SectionLabel>
      <div className="flex items-center gap-5 mb-4">
        <DonutChart
          entries={profile.formatBreakdown.map((f) => ({
            key: f.formatLabel,
            value: f.scoreContribution / total,
            color: FMT_COLORS[f.formatLabel] ?? "#5c8aff",
          }))}
          radius={56}
          strokeWidth={18}
          size={148}
          topLabel={fmtPts(profile.score)}
          topFontSize={28}
          bottomLabel="PTS"
          bottomFontSize={11}
        />
        <FormatLegend breakdown={profile.formatBreakdown} totalScore={profile.score} />
      </div>

      <SectionLabel size={13} className="mt-6 mb-3">DECKS BY ARCHETYPE</SectionLabel>
      <DonutChart
        entries={archEntries.map(([k, v], i) => ({
          key: k,
          value: v,
          color: ARCH_PALETTE[i % ARCH_PALETTE.length],
        }))}
        topLabel={archTotal}
        bottomLabel="DECKS"
      />
      <div className="flex flex-col gap-1 mt-2">
        {archEntries.slice(0, 6).map(([code, count], i) => (
          <div
            key={code}
            className="grid gap-2 items-center"
            style={{ gridTemplateColumns: "auto auto 1fr auto auto" }}
          >
            <span
              className="w-2 h-2 inline-block"
              style={{ background: ARCH_PALETTE[i % ARCH_PALETTE.length] }}
            />
            <Pips colors={code} size={12} />
            <span className="font-display text-[13px] tracking-[0.06em]">{code}</span>
            <TrophyCount count={archTrophies[code] ?? 0} size="sm" className="text-muted" />
            <span className="mono text-[11px] text-muted text-right" style={{ minWidth: 28 }}>
              ×{count}
            </span>
          </div>
        ))}
      </div>

      <SectionLabel size={13} className="mt-6 mb-3">COLORS PLAYED</SectionLabel>
      <div className="flex items-center gap-[18px]">
        <DonutChart
          entries={Object.entries(colorCount)
            .filter(([, v]) => v > 0)
            .map(([k, v]) => ({ key: k, value: v, color: COLOR_STROKES[k] }))}
          topLabel={colorTotal}
          bottomLabel="PIPS"
        />
        <div className="flex-1 grid grid-cols-5 gap-1">
          {COLOR_KEYS.map((c) => {
            const pct = (colorCount[c] / colorTotal) * 100;
            return (
              <div key={c} className="flex flex-col items-center py-2 px-1 border border-border">
                <span
                  className="w-[18px] h-[18px] rounded-full inline-block"
                  style={{ background: COLOR_STROKES[c] }}
                />
                <span className="font-display text-[14px] mt-1">{c}</span>
                <span className="mono text-[9px] text-muted">{pct.toFixed(0)}%</span>
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
}: {
  breakdown: PlayerFormatBreakdown[];
  totalScore: number;
}) {
  return (
    <div className="flex-1 flex flex-col">
      {breakdown.map((f, i) => {
        const pct = totalScore ? (f.scoreContribution / totalScore) * 100 : 0;
        return (
          <div
            key={f.formatLabel}
            className={cn(
              "grid items-baseline py-[5px] gap-2.5",
              i < breakdown.length - 1 && "border-b border-border",
            )}
            style={{ gridTemplateColumns: "1fr auto auto auto" }}
          >
            <span
              className="font-display text-[13px] tracking-[0.06em]"
              style={{ color: FMT_COLORS[f.formatLabel] ?? "#5c8aff" }}
            >
              {f.formatLabel.toUpperCase()}
            </span>
            <TrophyCount count={f.trophies} size="sm" className="text-muted" />
            <Record
              mono
              wins={f.wins}
              losses={f.losses}
              className="mono text-[11px] text-right text-muted"
              style={{ minWidth: 48 }}
            />
            <span
              className={cn(
                "font-display text-[14px] text-right",
                pct > 0 ? "text-green" : "text-muted",
              )}
              style={{ minWidth: 40 }}
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
  archFilter,
  setArchFilter,
}: {
  events: PlayerDraftEvent[];
  filtered: PlayerDraftEvent[];
  formatFilter: string;
  setFormatFilter: (v: string) => void;
  archFilter: string;
  setArchFilter: (v: string) => void;
}) {
  return (
    <section className="py-6 px-10">
      <div className="flex justify-between items-center">
        <SectionLabel size={13}>
          DRAFT LOG · {filtered.length} OF {events.length}
        </SectionLabel>
        <div className="flex gap-2">
          <FilterDropdown
            label="FORMAT"
            value={formatFilter}
            onChange={setFormatFilter}
            options={FORMAT_OPTIONS_LONG}
          />
          <FilterDropdown
            label="ARCHETYPE"
            value={archFilter}
            onChange={setArchFilter}
            options={ARCHETYPE_OPTIONS_LONG}
          />
        </div>
      </div>

      <div className="mt-3">
        {filtered.map((e) => (
          <div
            key={e.eventId}
            className="grid gap-3 py-[11px] border-b border-border items-center"
            style={{ gridTemplateColumns: "30px 110px 110px 1fr 90px" }}
          >
            <span className="text-center">
              {e.isTrophy ? <Trophy size={18} color="#ffc63a" /> : <span className="text-dim">·</span>}
            </span>
            <span className="mono text-[11px] text-muted">
              {e.finishedAt.slice(5, 10)} {e.finishedAt.slice(11, 16)}
            </span>
            <span className="font-display text-[14px] tracking-[0.08em]">
              {e.format.replace("Draft", "").toUpperCase()}
            </span>
            <span className="flex items-center gap-2">
              <Pips colors={e.colors} size={13} />
              <span className="mono text-[11px] text-muted">{e.colors}</span>
            </span>
            <Record
              mono
              wins={e.wins}
              losses={e.losses}
              color={e.wins >= 4 ? "#2ee85c" : "#e6ecf5"}
              className="text-right font-display text-[22px]"
            />
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="p-6 text-center text-muted font-display tracking-[0.2em]">
            NO EVENTS MATCH FILTER
          </div>
        )}
      </div>
    </section>
  );
}

// ─── Mobile ────────────────────────────────────────────────────────────────

function Mobile({ profile, events }: { profile: PlayerProfile; events: PlayerDraftEvent[] }) {
  const navigate = useNavigate();
  const wp = winPct(profile.wins, profile.losses);

  return (
    <div className="bg-bg text-text min-h-screen">
      <header className="py-3 px-[18px] border-b border-border flex items-center justify-between">
        <BackButton onClick={() => navigate(-1)} compact />
      </header>

      <section
        className="px-[18px] pt-5 pb-[22px] border-b border-border"
        style={{ background: "linear-gradient(180deg, #14181f 0%, #0a0c10 100%)" }}
      >
        <div className="flex items-center gap-4">
          <AAvatar displayName={profile.displayName} avatarUrl={profile.avatarUrl} size={84} green />
          <div className="flex-1 min-w-0">
            <SectionLabel size={11} letterSpacing="0.2em">PLAYER</SectionLabel>
            <h1
              className="font-display text-[36px] tracking-[0.03em] m-0 break-words"
              style={{ lineHeight: 0.95 }}
            >
              {profile.displayName.toUpperCase()}
            </h1>
            <div className="mt-1.5 flex items-center gap-2 font-display tracking-[0.18em]">
              <SetGlyph code={profile.setCode} size={18} />
              <span className="text-[14px]">{profile.setCode}</span>
              <span className="text-[11px] text-dim">·</span>
              <span className="text-[14px]">#{profile.rank}</span>
            </div>
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

      <section className="py-4 px-[18px]">
        <SectionLabel size={12} className="mb-2.5">
          RECENT DRAFTS · {events.length} EVENTS
        </SectionLabel>
        {events.slice(0, 20).map((e) => (
          <div
            key={e.eventId}
            className="grid gap-2.5 py-2.5 border-b border-border items-center"
            style={{ gridTemplateColumns: "20px 1fr auto" }}
          >
            <span>
              {e.isTrophy ? <Trophy size={16} color="#ffc63a" /> : <span className="text-dim">·</span>}
            </span>
            <div>
              <div className="flex items-center gap-1.5">
                <Pips colors={e.colors} size={11} />
                <span className="font-display text-[13px] tracking-[0.08em]">
                  {e.format.replace("Draft", "").toUpperCase()}
                </span>
              </div>
              <div className="mono text-[9px] text-muted mt-0.5">
                {e.colors} · {e.finishedAt.slice(5, 10)}
              </div>
            </div>
            <Record
              mono
              wins={e.wins}
              losses={e.losses}
              color={e.wins >= 4 ? "#2ee85c" : "#e6ecf5"}
              className="mono text-[14px] font-semibold"
            />
          </div>
        ))}
      </section>
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function BackButton({ onClick, compact = false }: { onClick: () => void; compact?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "bg-transparent border-none text-muted font-display text-[12px] cursor-pointer flex items-center",
        compact ? "tracking-[0.15em] gap-1.5" : "tracking-[0.18em] mb-3.5",
      )}
    >
      <span>‹</span> {compact ? "BACK" : "BACK TO LEADERBOARD"}
    </button>
  );
}
