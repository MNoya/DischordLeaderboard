import { useMemo, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { PageShell } from "../components/PageShell";
import { Container } from "../components/Container";
import { EpisodeCard } from "../components/EpisodeCard";
import { ChamferedButton } from "../components/ChamferedButton";
import { useEpisodes } from "../data/hooks";
import { EPISODE_CATEGORIES, type Episode, type EpisodeCategory } from "../data/episodes";
import { cn } from "../lib/utils";

type SortKey = "newest" | "oldest" | "longest";

const PAGE_SIZE = 12;

export function EpisodesPage() {
  const { data: episodes, isLoading, isError } = useEpisodes();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("newest");
  const [visible, setVisible] = useState(PAGE_SIZE);

  const activeCategory = (params.get("category") as EpisodeCategory | null) ?? null;

  const setCategory = (category: EpisodeCategory | null) => {
    const next = new URLSearchParams(params);
    if (category) {
      next.set("category", category);
    } else {
      next.delete("category");
    }
    setParams(next, { replace: true });
    setVisible(PAGE_SIZE);
  };

  const all = episodes ?? [];
  const counts = useMemo(() => {
    const map = new Map<EpisodeCategory, number>();
    for (const ep of all) {
      map.set(ep.category, (map.get(ep.category) ?? 0) + 1);
    }
    return map;
  }, [all]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = all.filter((ep) => {
      if (activeCategory && ep.category !== activeCategory) {
        return false;
      }
      if (needle && !ep.title.toLowerCase().includes(needle) && !ep.summary.toLowerCase().includes(needle)) {
        return false;
      }
      return true;
    });
    return sortEpisodes(rows, sort);
  }, [all, activeCategory, query, sort]);

  return (
    <PageShell subtitle="EPISODES">
      <Container className="pt-8 md:pt-12">
        <h1 className="font-display text-text text-[34px] md:text-[44px] tracking-[0.03em] leading-none">Episodes</h1>
        <p className="text-muted text-[14px] mt-2">
          {all.length ? `${all.length} episodes · ` : ""}every set since 2020
        </p>

        <div className="flex flex-col md:flex-row gap-3 mt-6">
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setVisible(PAGE_SIZE);
            }}
            placeholder="Search episodes, sets, or guests…"
            className="flex-1 bg-surface border border-border px-4 py-2.5 text-[14px] text-text placeholder:text-dim outline-none transition-colors focus:border-green"
          />
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="bg-surface border border-border px-4 py-2.5 text-[14px] text-text outline-none transition-colors focus:border-green font-display tracking-[0.06em]"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="longest">Longest first</option>
          </select>
        </div>

        <div className="flex flex-wrap gap-2 mt-4">
          <FilterPill label="All" count={all.length} active={!activeCategory} onClick={() => setCategory(null)} />
          {EPISODE_CATEGORIES.map((category) => (
            <FilterPill
              key={category}
              label={category}
              count={counts.get(category) ?? 0}
              active={activeCategory === category}
              onClick={() => setCategory(category)}
            />
          ))}
        </div>
      </Container>

      <Container className="pt-8 pb-4 border-t border-border mt-6">
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
            <Grid>
              {filtered.slice(0, visible).map((ep) => (
                <EpisodeCard key={ep.id} episode={ep} />
              ))}
            </Grid>
            {visible < filtered.length ? (
              <div className="flex justify-center mt-10">
                <ChamferedButton onClick={() => setVisible((v) => v + PAGE_SIZE)}>LOAD MORE EPISODES</ChamferedButton>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-muted text-[14px] py-8">No episodes match that search.</p>
        )}
      </Container>
    </PageShell>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-10">{children}</div>;
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
