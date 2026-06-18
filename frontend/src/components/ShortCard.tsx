import { useState } from "react";

import type { Episode } from "../data/episodes";
import { EpisodeThumbnail } from "./EpisodeThumbnail";

export function ShortCard({ episode, thumbnailPending = false }: { episode: Episode; thumbnailPending?: boolean }) {
  const [playing, setPlaying] = useState(false);
  const canEmbed = Boolean(episode.youtubeId);

  return (
    <div className="group flex flex-col">
      <div className="relative aspect-[9/16] bg-surface border border-border rounded-lg overflow-hidden transition-[border-color,box-shadow] duration-150 group-hover:border-green group-hover:shadow-[0_0_11px_2px_rgba(46,232,92,0.55)]">
        {playing && canEmbed ? (
          <iframe
            src={`https://www.youtube.com/embed/${episode.youtubeId}?autoplay=1&playsinline=1&rel=0`}
            title={episode.title}
            className="absolute inset-0 h-full w-full"
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
            allowFullScreen
          />
        ) : canEmbed ? (
          <button
            type="button"
            onClick={() => setPlaying(true)}
            aria-label={`Play ${episode.title}`}
            className="absolute inset-0 block w-full cursor-pointer"
          >
            <ShortThumbnail episode={episode} thumbnailPending={thumbnailPending} />
          </button>
        ) : (
          <a href={episode.link} target="_blank" rel="noreferrer" className="absolute inset-0 block w-full">
            <ShortThumbnail episode={episode} thumbnailPending={thumbnailPending} />
          </a>
        )}
      </div>
      <a
        href={episode.videoUrl ?? episode.link}
        target="_blank"
        rel="noreferrer"
        className="font-body text-text text-[14px] font-medium leading-snug mt-2 line-clamp-2 no-underline transition-colors group-hover:text-green"
      >
        {episode.title}
      </a>
    </div>
  );
}

function ShortThumbnail({ episode, thumbnailPending }: { episode: Episode; thumbnailPending: boolean }) {
  return (
    <>
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
    </>
  );
}
