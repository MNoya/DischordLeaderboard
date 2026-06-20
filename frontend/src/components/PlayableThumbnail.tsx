import { useState } from "react";

import type { Episode } from "../data/episodes";
import { EpisodeThumbnail } from "./EpisodeThumbnail";
import { PodcastAudioPlayer } from "./PodcastAudioPlayer";
import { Headphones, Music, Play } from "./Icons";
import { PlayBadge } from "./PlayBadge";
import { cn } from "../lib/utils";

export function PlayableThumbnail({
  episode,
  thumbnailPending = false,
  aspect,
  audioMode = false,
  portrait = false,
}: {
  episode: Episode;
  thumbnailPending?: boolean;
  aspect: string;
  audioMode?: boolean;
  portrait?: boolean;
}) {
  const [playing, setPlaying] = useState(false);
  const { canPlayAudio, playable } = episodePlayability(episode, audioMode);

  return (
    <div
      className={cn(
        "relative bg-surface border border-border rounded-lg overflow-hidden transition-[border-color,box-shadow] duration-150 group-hover:border-green group-hover:shadow-[0_0_8px_1px_rgba(46,232,92,0.32)]",
        aspect,
      )}
    >
      {playing ? (
        <EpisodeEmbed episode={episode} thumbnailPending={thumbnailPending} audioMode={audioMode} />
      ) : playable ? (
        <button
          type="button"
          onClick={() => setPlaying(true)}
          aria-label={`Play ${episode.title}`}
          className="absolute inset-0 block w-full cursor-pointer"
        >
          <ThumbnailInner episode={episode} thumbnailPending={thumbnailPending} audio={canPlayAudio} portrait={portrait} />
        </button>
      ) : (
        <a href={episode.link} target="_blank" rel="noreferrer" className="absolute inset-0 block w-full">
          <ThumbnailInner episode={episode} thumbnailPending={thumbnailPending} audio={false} portrait={portrait} />
        </a>
      )}
    </div>
  );
}

export function episodePlayability(episode: Episode, audioMode = false) {
  const hasVideo = Boolean(episode.youtubeId);
  const hasAudio = Boolean(episode.audioUrl);
  const canEmbed = hasVideo && !audioMode;
  const canPlayAudio = hasAudio && (audioMode || !hasVideo);
  return { canEmbed, canPlayAudio, playable: canEmbed || canPlayAudio };
}

export function EpisodeEmbed({
  episode,
  thumbnailPending = false,
  audioMode = false,
}: {
  episode: Episode;
  thumbnailPending?: boolean;
  audioMode?: boolean;
}) {
  const [embedLoaded, setEmbedLoaded] = useState(false);
  if (episode.youtubeId && !audioMode) {
    return (
      <>
        <iframe
          src={`https://www.youtube.com/embed/${episode.youtubeId}?autoplay=1&playsinline=1&rel=0`}
          title={episode.title}
          className="absolute inset-0 h-full w-full"
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
          onLoad={() => setEmbedLoaded(true)}
        />
        {embedLoaded ? null : (
          <div className="absolute inset-0">
            <EpisodeThumbnail pending />
          </div>
        )}
      </>
    );
  }
  return (
    <>
      <EpisodeThumbnail
        src={episode.image}
        pending={thumbnailPending}
        className="transition-transform duration-300 scale-[1.07]"
      />
      <PodcastAudioPlayer src={episode.audioUrl} title={episode.title} />
    </>
  );
}

function ThumbnailInner({
  episode,
  thumbnailPending,
  audio,
  portrait,
}: {
  episode: Episode;
  thumbnailPending: boolean;
  audio: boolean;
  portrait: boolean;
}) {
  const audioOnly = !episode.youtubeId && Boolean(episode.audioUrl);
  return (
    <>
      <EpisodeThumbnail
        src={episode.image}
        pending={thumbnailPending}
        portrait={portrait}
        className="transition-transform duration-300 group-hover:scale-[1.07]"
      />
      {audioOnly || episode.durationLabel ? (
        <span className="absolute bottom-2 right-2 flex items-center gap-1.5 mono text-[11px] text-text bg-bg/85 px-1.5 py-0.5">
          {audioOnly ? <Headphones size={12} /> : null}
          {episode.durationLabel ? episode.durationLabel : null}
        </span>
      ) : null}
      <span className="absolute inset-0 flex items-center justify-center bg-bg/30 opacity-0 transition-opacity group-hover:opacity-100">
        <PlayBadge>
          {audio ? <Music size={24} /> : <Play size={32} />}
        </PlayBadge>
      </span>
    </>
  );
}
