import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { setGlyphCode } from "../components/Brand";
import { TierFilterBar } from "../components/TierFilterBar";
import { TierGrid } from "../components/TierGrid";
import { TierSetDropdown } from "../components/TierSetDropdown";
import { useSets } from "../data/hooks";
import { relativeTime } from "../data/utils";
import { cn } from "../lib/utils";
import { useIsMobile } from "../lib/use-is-mobile";
import {
  ACTIVE_SET_CODE,
  TIER_LIST_GRADERS,
  TIER_LIST_PREVIEW_SETS,
  TIER_LIST_UIDS,
} from "../data/constants";
import {
  EMPTY_FILTERS,
  hasActiveFilters,
  tierFilterOptions,
  useTierList,
  type TierFilters,
} from "../data/tierList";
import type { SetSummary } from "../types/leaderboard";

export function TierListPage() {
  const { data: sets } = useSets();
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { setCode } = useParams();
  const [filters, setFilters] = useState<TierFilters>(EMPTY_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [headerHeight, setHeaderHeight] = useState(0);
  const headerRef = useRef<HTMLDivElement>(null);

  const activeFilterCount =
    filters.sets.length +
    filters.manaValues.length +
    filters.rarities.length +
    filters.cardTypes.length +
    filters.trends.length;

  const liveSet = sets?.find((s) => s.isActive)?.code ?? ACTIVE_SET_CODE;
  const tierListSets = useMemo(() => buildTierListSets(sets), [sets]);
  const current = setCode?.toUpperCase() ?? tierListSets[0]?.code ?? liveSet;
  const pickSet = (code: string) => navigate(`/tier-list/${code}`);
  const setMeta = tierListSets.find((s) => s.code === current);
  const uid = TIER_LIST_UIDS[current];
  const graders = TIER_LIST_GRADERS[current] ?? [];
  const glyphCode = setMeta ? setGlyphCode(setMeta) : current;

  const { data: tierData, lastUpdated } = useTierList(uid);
  const filterOptions = useMemo(
    () => tierFilterOptions(tierData ?? []),
    [tierData],
  );
  const filtersReady = Boolean(tierData?.length);

  useEffect(() => {
    setFilters(EMPTY_FILTERS);
  }, [uid]);

  useEffect(() => {
    const header = headerRef.current;
    if (!header) return;
    const ro = new ResizeObserver(() => setHeaderHeight(header.offsetHeight));
    ro.observe(header);
    setHeaderHeight(header.offsetHeight);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="bg-bg text-text min-h-screen flex flex-col animate-fadeIn">
      <AppHeader subtitle="TIER LIST" />
      <main className="flex flex-col w-full px-2 md:px-[15px] pb-4 overflow-x-clip">
        <div ref={headerRef} className="sticky top-0 z-20 bg-bg py-2 md:py-3">
          {isMobile ? (
            <>
              <div className="flex items-center gap-x-5 gap-y-2">
                <h1 className="font-display tracking-[0.12em] flex flex-1 items-center gap-2 leading-none min-w-0">
                  <TierSetDropdown
                    sets={tierListSets}
                    activeCode={current}
                    glyphCode={glyphCode}
                    label={setMeta?.name?.toUpperCase() ?? current}
                    isMobile
                    onChange={pickSet}
                  />
                </h1>

                {uid && filtersReady && (
                  <button
                    type="button"
                    onClick={() => setFiltersOpen((open) => !open)}
                    aria-expanded={filtersOpen}
                    className={cn(
                      "flex h-9 shrink-0 items-center gap-1.5 rounded border px-2.5 text-[12px] transition-colors",
                      filtersOpen || hasActiveFilters(filters)
                        ? "border-green text-text"
                        : "border-border2 text-muted",
                    )}
                  >
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path
                        d="M3 5h18l-7 8v6l-4-2v-4z"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Filters
                    {activeFilterCount > 0 && (
                      <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-green px-1 text-[10px] font-bold text-bg">
                        {activeFilterCount}
                      </span>
                    )}
                    <span
                      className={cn(
                        "text-[10px] transition-transform",
                        filtersOpen && "rotate-180",
                      )}
                    >
                      ▾
                    </span>
                  </button>
                )}
              </div>

              <ListMeta lastUpdated={lastUpdated} className="mt-1.5" />

              {uid && filtersReady && filtersOpen && (
                <div className="pt-3">
                  <TierFilterBar
                    filters={filters}
                    setFilters={setFilters}
                    options={filterOptions}
                    setCode={glyphCode}
                    stacked
                  />
                </div>
              )}
            </>
          ) : (
            <div className="grid items-center gap-x-[clamp(0.75rem,2.5vw,2.5rem)] grid-cols-[minmax(0,1fr)_auto] min-[1500px]:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
              <div className="min-w-0">
                <h1 className="font-display tracking-[0.12em] flex items-center gap-3 leading-none min-w-0">
                  <TierSetDropdown
                    sets={tierListSets}
                    activeCode={current}
                    glyphCode={glyphCode}
                    label={setMeta?.name?.toUpperCase() ?? current}
                    isMobile={false}
                    onChange={pickSet}
                  />
                </h1>
                <ListMeta lastUpdated={lastUpdated} className="mt-1 pl-[2px]" />
              </div>

              {uid && filtersReady ? (
                <div className="justify-self-center -translate-y-1">
                  <TierFilterBar
                    filters={filters}
                    setFilters={setFilters}
                    options={filterOptions}
                    setCode={glyphCode}
                  />
                </div>
              ) : (
                <div />
              )}

              <div className="hidden min-[1500px]:block" />
            </div>
          )}
        </div>

        {uid ? (
          <TierGrid
            uid={uid}
            graders={graders}
            filters={filters}
            stickyTop={headerHeight}
          />
        ) : (
          <div className="flex items-center justify-center border border-border bg-surface text-muted text-[14px] min-h-[300px]">
            No tier list is available for {current} yet.
          </div>
        )}

        <div className="pt-2 text-right">
          <a
            href={`https://www.17lands.com/tier_list/${uid ?? ""}`}
            target="_blank"
            rel="noreferrer"
            className="mono text-[10px] md:text-[12px] text-muted hover:text-green transition-colors no-underline"
          >
            via 17Lands
          </a>
        </div>
      </main>
    </div>
  );
}

function ListMeta({
  lastUpdated,
  className,
}: {
  lastUpdated: string | null;
  className?: string;
}) {
  const rel = lastUpdated ? relativeTime(lastUpdated) : null;
  const updated =
    rel === null ? null : rel === "now" ? "UPDATED JUST NOW" : `LAST UPDATED ${rel.toUpperCase()} AGO`;
  return (
    <div className={cn("mono text-[11px] tracking-[0.16em] text-muted", className)}>
      SET REVIEW GRADES{updated ? ` · ${updated}` : ""}
    </div>
  );
}

function buildTierListSets(sets: SetSummary[] | undefined): SetSummary[] {
  const live = (sets ?? []).filter((s) => TIER_LIST_UIDS[s.code]);
  const liveCodes = new Set(live.map((s) => s.code));
  const previews = Object.entries(TIER_LIST_PREVIEW_SETS)
    .filter(([code]) => TIER_LIST_UIDS[code] && !liveCodes.has(code))
    .map(
      ([code, info]): SetSummary => ({
        code,
        name: info.name,
        startDate: info.startDate,
        endDate: "",
        isActive: false,
      }),
    );
  return [...previews, ...live].sort((a, b) =>
    b.startDate.localeCompare(a.startDate),
  );
}
