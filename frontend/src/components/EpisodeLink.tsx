import type { ReactNode } from "react";

import type { Episode } from "../data/episodes";
import { useIsMobile } from "../lib/use-is-mobile";
import { Tooltip } from "./Tooltip";

export function episodeTitleHref(episode: Episode, audioMode = false): string {
  return !audioMode && episode.videoUrl ? episode.videoUrl : episode.link;
}

export function episodeLinkTooltip(episode: Episode, audioMode = false): string {
  return !audioMode && episode.videoUrl ? "Watch on YouTube" : "Listen on Libsyn";
}

// Hover hint over an episode's title link, naming the destination. Skipped on mobile,
// where there's no hover and a tap would otherwise fire the tooltip before the link.
export function EpisodeLinkTooltip({
  episode,
  audioMode = false,
  children,
}: {
  episode: Episode;
  audioMode?: boolean;
  children: ReactNode;
}) {
  const isMobile = useIsMobile();
  if (isMobile) return <>{children}</>;
  return (
    <Tooltip label={episodeLinkTooltip(episode, audioMode)} side="top" align="center">
      {children}
    </Tooltip>
  );
}
