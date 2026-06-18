import type { Episode } from "../data/episodes";
import { PlayableThumbnail } from "./PlayableThumbnail";

export function ShortCard({ episode, thumbnailPending = false }: { episode: Episode; thumbnailPending?: boolean }) {
  return (
    <div className="group flex flex-col">
      <PlayableThumbnail episode={episode} thumbnailPending={thumbnailPending} aspect="aspect-[9/16]" portrait />
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
