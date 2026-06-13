import { SiYoutube } from "react-icons/si";
import type { Episode } from "../data/episodes";
import { CategoryTag } from "./CategoryTag";
import { EpisodeThumbnail } from "./EpisodeThumbnail";

export function EpisodeCard({ episode, thumbnailPending = false }: { episode: Episode; thumbnailPending?: boolean }) {
  const meta = [episode.publishedLabel.toUpperCase(), episode.number ? `EP ${episode.number}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <a href={episode.link} target="_blank" rel="noreferrer" className="group flex flex-col no-underline">
      <div className="relative aspect-video bg-surface border border-border overflow-hidden transition-colors group-hover:border-green">
        <EpisodeThumbnail src={episode.image} pending={thumbnailPending} />
        {episode.kind === "video" ? (
          <span className="absolute top-2 right-2 inline-flex items-center gap-1 mono text-[10px] tracking-[0.08em] text-text bg-red px-1.5 py-0.5">
            <SiYoutube className="text-[11px]" /> VIDEO
          </span>
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
