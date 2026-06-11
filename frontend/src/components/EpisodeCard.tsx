import type { Episode } from "../data/episodes";
import { CategoryTag } from "./CategoryTag";

// Cover thumbnail + meta + title + category tag. Reused by the home recent-grid
// and the episodes archive; sizing is driven by its grid cell, not the card.
export function EpisodeCard({ episode }: { episode: Episode }) {
  const meta = [episode.publishedLabel.toUpperCase(), episode.number ? `EP ${episode.number}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <a href={episode.link} target="_blank" rel="noreferrer" className="group flex flex-col no-underline">
      <div className="relative aspect-video bg-surface border border-border overflow-hidden transition-colors group-hover:border-green">
        {episode.image ? (
          <img src={episode.image} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : null}
        {episode.durationLabel ? (
          <span className="absolute bottom-2 right-2 mono text-[11px] text-text bg-bg/85 px-1.5 py-0.5">
            {episode.durationLabel}
          </span>
        ) : null}
        <span className="absolute inset-0 flex items-center justify-center bg-bg/40 opacity-0 transition-opacity group-hover:opacity-100">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-green text-bg pl-0.5 text-[18px]">
            ▶
          </span>
        </span>
      </div>
      <div className="mono text-[11px] tracking-[0.12em] text-muted mt-3">{meta}</div>
      <h3 className="font-body text-text text-[15px] md:text-[16px] font-medium leading-snug mt-1.5 line-clamp-2 transition-colors group-hover:text-green">
        {episode.title}
      </h3>
      <div className="mt-2.5">
        <CategoryTag category={episode.category} />
      </div>
    </a>
  );
}
