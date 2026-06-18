import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { SiApplepodcasts, SiRss, SiSpotify, SiYoutube } from "react-icons/si";
import type { IconType } from "react-icons";
import { PageShell } from "../components/PageShell";
import { EpisodeCard } from "../components/EpisodeCard";
import { ShortCard } from "../components/ShortCard";
import { FilterDropdown, type FilterOption } from "../components/FilterDropdown";
import { GoToTopButton } from "../components/GoToTopButton";
import { SetGlyph } from "../components/Brand";
import { useMediaFeed } from "../data/hooks";
import { EPISODE_CATEGORIES, type Episode, type EpisodeCategory } from "../data/episodes";
import { LISTEN_ON } from "../data/site";
import { cn } from "../lib/utils";
import { TOGGLE_ACTIVE, TOGGLE_INACTIVE } from "../lib/toggle-styles";

const SORT_OPTIONS: FilterOption[] = [
  { value: "newest", label: "Newest" },
  { value: "oldest", label: "Oldest" },
  { value: "longest", label: "Longest" },
];

const renderSetValue = (option: FilterOption) =>
  option.value ? (
    <span className="flex items-center gap-2 truncate">
      <SetGlyph code={option.value} size={20} />
      {option.label}
    </span>
  ) : (
    option.label
  );

const LISTEN_ICONS: Record<string, IconType> = {
  Apple: SiApplepodcasts,
  Spotify: SiSpotify,
  YouTube: SiYoutube,
  RSS: SiRss,
};

type SortKey = "newest" | "oldest" | "longest";

const PAGE_SIZE = 12;

const setCodeOf = (ep: Episode) => ep.setCode ?? null;
const setNameOf = (ep: Episode) => ep.setName ?? ep.setCode ?? "";

export function EpisodesPage() {
  const { data: episodes, isLoading, isError, thumbnailsPending } = useMediaFeed();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [visible, setVisible] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const shortsView = params.get("type") === "shorts";
  const activeCategory = (params.get("category") as EpisodeCategory | null) ?? null;
  const activeSet = params.get("set");

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    setParams(next, { replace: true });
    setVisible(PAGE_SIZE);
  };
  const setCategory = (category: EpisodeCategory | null) => {
    const next = new URLSearchParams(params);
    next.delete("type");
    if (category) {
      next.set("category", category);
    } else {
      next.delete("category");
    }
    setParams(next, { replace: true });
    setVisible(PAGE_SIZE);
  };
  const showShorts = () => {
    const next = new URLSearchParams(params);
    next.set("type", "shorts");
    next.delete("category");
    setParams(next, { replace: true });
    setVisible(PAGE_SIZE);
  };

  const all = episodes ?? [];
  const longform = useMemo(() => all.filter((ep) => !ep.isShort), [all]);
  const shorts = useMemo(() => all.filter((ep) => ep.isShort), [all]);
  const pool = shortsView ? shorts : longform;

  const longformInSet = useMemo(
    () => (activeSet ? longform.filter((ep) => setCodeOf(ep) === activeSet) : longform),
    [longform, activeSet],
  );
  const shortsInSet = useMemo(
    () => (activeSet ? shorts.filter((ep) => setCodeOf(ep) === activeSet) : shorts),
    [shorts, activeSet],
  );

  const counts = useMemo(() => {
    const map = new Map<EpisodeCategory, number>();
    for (const ep of longformInSet) {
      map.set(ep.category, (map.get(ep.category) ?? 0) + 1);
    }
    return map;
  }, [longformInSet]);

  const setMeta = useMemo(() => {
    const map = new Map<string, { name: string; count: number; released: string | null }>();
    for (const ep of pool) {
      const code = ep.setCode;
      if (!code) {
        continue;
      }
      const entry = map.get(code);
      if (entry) {
        entry.count += 1;
        entry.released = entry.released ?? ep.setReleasedAt ?? null;
      } else {
        map.set(code, { name: setNameOf(ep), count: 1, released: ep.setReleasedAt ?? null });
      }
    }
    return map;
  }, [pool]);

  const setFilterOptions = useMemo<FilterOption[]>(() => {
    const entries = [...setMeta.entries()].sort((a, b) => compareReleaseDesc(a[1].released, b[1].released));
    return [
      { value: "", label: "All sets" },
      ...entries.map(([code, meta]) => ({ value: code, label: meta.name })),
    ];
  }, [setMeta]);

  const renderSetOption = (option: FilterOption) => {
    const count = option.value ? setMeta.get(option.value)?.count : pool.length;
    return (
      <span className="flex w-full min-w-0 items-center gap-2.5">
        {option.value ? <SetGlyph code={option.value} size={20} /> : <span className="w-5 shrink-0" />}
        <span className="flex-1 truncate">{option.label}</span>
        {count != null && <span className="mono text-[12px] tabular-nums text-muted shrink-0">{count}</span>}
      </span>
    );
  };

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = pool.filter((ep) => {
      if (!shortsView && activeCategory && ep.category !== activeCategory) {
        return false;
      }
      if (activeSet && setCodeOf(ep) !== activeSet) {
        return false;
      }
      if (needle && !ep.title.toLowerCase().includes(needle) && !ep.summary.toLowerCase().includes(needle)) {
        return false;
      }
      return true;
    });
    return sortEpisodes(rows, sort);
  }, [pool, shortsView, activeCategory, activeSet, query, sort]);

  useEffect(() => {
    if (visible >= filtered.length) {
      return;
    }
    const sentinel = sentinelRef.current;
    if (!sentinel) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisible((current) => Math.min(current + PAGE_SIZE, filtered.length));
        }
      },
      { rootMargin: "600px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [visible, filtered.length]);

  return (
    <PageShell subtitle="EPISODES">
      <div className="border-b border-border bg-surface px-4 md:px-10 py-4 flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <FilterDropdown
            label="SET"
            value={activeSet ?? ""}
            options={setFilterOptions}
            onChange={(v) => setParam("set", v || null)}
            renderValue={renderSetValue}
            renderOption={renderSetOption}
            searchPlaceholder="Search sets or codes…"
            className="order-1 flex-1 min-w-0 md:flex-none"
            triggerClassName={cn("w-full !min-w-0 md:!min-w-[240px]", activeSet && TOGGLE_ACTIVE)}
          />
          <SortControl
            value={sort}
            onChange={setSort}
            className="order-2 md:order-3 flex-1 min-w-0 md:flex-none"
          />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setVisible(PAGE_SIZE);
            }}
            placeholder="Search episodes, sets, or guests…"
            className="order-3 w-full md:order-2 md:flex-1 md:w-auto bg-bg border border-border2 px-3.5 py-2 text-[14px] text-text placeholder:text-dim outline-none transition-colors focus:border-green"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <FilterPill
            label="All"
            count={longformInSet.length}
            active={!shortsView && !activeCategory}
            onClick={() => setCategory(null)}
          />
          {(!activeSet || (counts.get("Evergreen") ?? 0) > 0) && (
            <FilterPill
              label="Evergreen"
              count={counts.get("Evergreen") ?? 0}
              active={!shortsView && activeCategory === "Evergreen"}
              onClick={() => setCategory("Evergreen")}
            />
          )}
          {EPISODE_CATEGORIES.filter((category) => category !== "Evergreen").map((category) => (
            <FilterPill
              key={category}
              label={category}
              count={counts.get(category) ?? 0}
              active={!shortsView && activeCategory === category}
              onClick={() => setCategory(category)}
            />
          ))}
          {shorts.length ? (
            <FilterPill label="Shorts" count={shortsInSet.length} active={shortsView} onClick={showShorts} />
          ) : null}
          <div className="ml-auto hidden md:flex items-center gap-2.5">
            <span className="mono text-[11px] tracking-[0.16em] text-dim uppercase hidden lg:inline">Listen on</span>
            {LISTEN_ON.map(({ label, url }) => {
              const Icon = LISTEN_ICONS[label];
              return (
                <a
                  key={label}
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={label}
                  className="inline-flex h-8 w-8 items-center justify-center border border-border2 text-subtle no-underline transition-colors hover:border-green hover:text-green"
                >
                  {Icon ? <Icon className="text-[15px]" size={15} /> : label}
                </a>
              );
            })}
          </div>
        </div>
      </div>

      <div className="px-4 md:px-10 pt-8 pb-4">
        {isLoading ? (
          <Grid>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-video bg-surface border border-border animate-pulse" />
            ))}
          </Grid>
        ) : isError ? (
          <p className="text-muted text-[14px] py-8">Couldn't reach the podcast feed. Refresh to try again.</p>
        ) : filtered.length ? (
          <>
            {shortsView ? (
              <ShortGrid>
                {filtered.slice(0, visible).map((ep) => (
                  <ShortCard key={ep.id} episode={ep} thumbnailPending={thumbnailsPending} />
                ))}
              </ShortGrid>
            ) : (
              <Grid>
                {filtered.slice(0, visible).map((ep) => (
                  <EpisodeCard key={ep.id} episode={ep} thumbnailPending={thumbnailsPending} />
                ))}
              </Grid>
            )}
            {visible < filtered.length ? (
              <div ref={sentinelRef} className="h-10 flex items-center justify-center mt-10">
                <span className="mono text-[11px] tracking-[0.16em] text-dim uppercase animate-pulse">Loading…</span>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-muted text-[14px] py-8">No {shortsView ? "shorts" : "episodes"} match that search.</p>
        )}
      </div>
      <GoToTopButton onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
    </PageShell>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-x-4 gap-y-7">
      {children}
    </div>
  );
}

function ShortGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-x-4 gap-y-8">
      {children}
    </div>
  );
}

function SortControl({
  value,
  onChange,
  className,
}: {
  value: SortKey;
  onChange: (value: SortKey) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex border border-border divide-x divide-border", className)}>
      {SORT_OPTIONS.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value as SortKey)}
            className={cn(
              "flex-1 px-3.5 py-2 font-display tracking-[0.06em] text-[14px] transition-colors md:flex-none",
              active ? TOGGLE_ACTIVE : TOGGLE_INACTIVE,
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function FilterPill({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 border px-3.5 py-1.5 font-display tracking-[0.06em] text-[14px] transition-colors",
        active
          ? "bg-green text-bg border-green"
          : "bg-transparent text-text border-border hover:border-green",
      )}
    >
      {label}
      <span className={cn("mono text-[11px] tabular-nums", active ? "text-bg/70" : "text-muted")}>{count}</span>
    </button>
  );
}

function compareReleaseDesc(a: string | null, b: string | null): number {
  if (a === b) {
    return 0;
  }
  if (!a) {
    return -1;
  }
  if (!b) {
    return 1;
  }
  return a < b ? 1 : -1;
}

function sortEpisodes(rows: Episode[], sort: SortKey): Episode[] {
  const sorted = [...rows];
  if (sort === "longest") {
    sorted.sort((a, b) => b.durationSeconds - a.durationSeconds);
    return sorted;
  }
  sorted.sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
  if (sort === "oldest") {
    sorted.reverse();
  }
  return sorted;
}
