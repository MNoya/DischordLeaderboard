import type { Episode } from "../data/episodes";
import { CategoryTag } from "./CategoryTag";
import { EpisodeThumbnail } from "./EpisodeThumbnail";

export function EpisodeCard({ episode, thumbnailPending = false }: { episode: Episode; thumbnailPending?: boolean }) {
  const meta = [episode.publishedLabel.toUpperCase(), episode.number ? `EP ${episode.number}` : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <a href={episode.videoUrl ?? episode.link} target="_blank" rel="noreferrer" className="group flex flex-col no-underline">
      <div className="relative aspect-video bg-surface border border-border rounded-lg overflow-hidden transition-[border-color,box-shadow] duration-150 group-hover:border-green group-hover:shadow-[0_0_11px_2px_rgba(46,232,92,0.55)]">
        <EpisodeThumbnail
          src={episode.image}
          pending={thumbnailPending}
          className="transition-transform duration-300 group-hover:scale-[1.07]"
        />
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
      <div className="flex items-center justify-between gap-2 mt-3">
        <span className="mono text-[11px] tracking-[0.12em] text-muted">{meta}</span>
        <CategoryTag category={episode.category} />
      </div>
      <h3 className="font-body text-text text-[15px] md:text-[16px] font-medium leading-snug mt-1.5 line-clamp-2 transition-colors group-hover:text-green">
        {episode.title}
      </h3>
    </a>
  );
}
