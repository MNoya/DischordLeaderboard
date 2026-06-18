import type { Episode } from "../data/episodes";
import { EpisodeTag } from "./CategoryTag";
import { PlayableThumbnail } from "./PlayableThumbnail";

export function EpisodeCard({
  episode,
  thumbnailPending = false,
  audioMode = false,
}: {
  episode: Episode;
  thumbnailPending?: boolean;
  audioMode?: boolean;
}) {
  const meta = [episode.publishedLabel.toUpperCase(), episode.number ? `EP ${episode.number}` : null]
    .filter(Boolean)
    .join(" · ");
  const titleHref = audioMode || episode.kind === "episode" ? episode.link : episode.videoUrl ?? episode.link;

  return (
    <div className="group flex flex-col">
      <PlayableThumbnail episode={episode} thumbnailPending={thumbnailPending} aspect="aspect-video" audioMode={audioMode} />
      <div className="flex items-center justify-between gap-2 mt-3">
        <span className="mono text-[11px] tracking-[0.12em] text-muted">{meta}</span>
        <EpisodeTag episode={episode} />
      </div>
      <a
        href={titleHref}
        target="_blank"
        rel="noreferrer"
        className="font-body text-text text-[15px] md:text-[16px] font-medium leading-snug mt-1.5 line-clamp-2 no-underline transition-colors group-hover:text-green"
      >
        {episode.title}
      </a>
    </div>
  );
}
