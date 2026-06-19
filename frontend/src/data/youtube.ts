// YouTube uploads pulled through the /api/youtube proxy (Cloudflare Function in
// prod, a vite dev plugin locally) since the Data API key can't ride in the
// browser. The proxy hands back already-normalized items; here we map them to
// the shared Episode shape and fold them into the Libsyn feed: a video that
// matches a podcast episode upgrades that episode's thumbnail, and the rest
// surface as standalone "video" cards in the same grid.

import {
  cleanTitle,
  formatDuration,
  formatPublished,
  inferCategory,
  isShortMedia,
  parseEpisodeNumber,
  type Episode,
} from "./episodes";

export const YOUTUBE_API_URL = "/api/youtube";

export interface YouTubeVideo {
  id: string;
  title: string;
  publishedAt: string;
  description: string;
  thumbnail: string;
  duration?: string;
}

export async function fetchYouTubeVideos(): Promise<YouTubeVideo[]> {
  const res = await fetch(YOUTUBE_API_URL);
  if (!res.ok) {
    throw new Error(`YouTube proxy responded ${res.status}`);
  }
  const json = (await res.json()) as { videos?: YouTubeVideo[] };
  return json.videos ?? [];
}

const MATCH_WINDOW_MS = 3 * 24 * 60 * 60 * 1000;

export function mergeMedia(episodes: Episode[], videos: YouTubeVideo[]): Episode[] {
  const claimed = new Set<string>();
  const enriched = episodes.map((episode) => {
    const match = findMatch(episode, videos, claimed);
    if (!match) {
      return episode;
    }
    claimed.add(match.id);
    return {
      ...episode,
      image: match.thumbnail || episode.image,
      youtubeId: match.id,
      videoUrl: watchUrl(match.id),
    };
  });

  const standalone = videos.filter((video) => !claimed.has(video.id)).map(toVideoEpisode);

  return [...enriched, ...standalone].sort(
    (a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime(),
  );
}

// DB rows are authoritative (categorized, set-tagged, thumbnails matched). Live RSS/YouTube
// items not yet synced overlay on top so a just-dropped episode shows up before the next sync,
// deduped against the DB by guid and by matched youtube id, and stamped with the latest release
// set as a best guess until the bot resolves the real one.
export function overlayLiveMedia(db: Episode[], live: Episode[]): Episode[] {
  const dbIds = new Set(db.map((e) => e.id));
  const dbYoutubeIds = new Set(db.map((e) => e.youtubeId).filter(Boolean));
  const assumedSet = latestReleaseSet(db);
  const fresh = live
    .filter((e) => !dbIds.has(e.id) && !(e.youtubeId && dbYoutubeIds.has(e.youtubeId)))
    .map((e) => withAssumedSet(e, assumedSet));
  return [...db, ...fresh].sort((a, b) => new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime());
}

// The set the newest set-tagged episode belongs to — what the bot's resolve_set would give a
// brand-new same-era drop. Tracks the previewing set, not the leaderboard's active set, which
// keeps running the prior set through a release window. Set-agnostic content has a null set_code.
function latestReleaseSet(db: Episode[]): Episode | undefined {
  let latest: Episode | undefined;
  for (const episode of db) {
    if (!episode.setCode) {
      continue;
    }
    if (!latest || new Date(episode.pubDate).getTime() > new Date(latest.pubDate).getTime()) {
      latest = episode;
    }
  }
  return latest;
}

function withAssumedSet(episode: Episode, source: Episode | undefined): Episode {
  if (!source || episode.setCode || episode.category === "Evergreen") {
    return episode;
  }
  return {
    ...episode,
    setCode: source.setCode,
    setName: source.setName,
    setReleasedAt: source.setReleasedAt,
  };
}

function findMatch(episode: Episode, videos: YouTubeVideo[], claimed: Set<string>): YouTubeVideo | null {
  const available = videos.filter((video) => !claimed.has(video.id));

  if (episode.number !== null) {
    const byNumber = available.find((video) => parseEpisodeNumber(video.title) === episode.number);
    if (byNumber) {
      return byNumber;
    }
  }

  const episodeKey = titleKey(episode.title);
  const byTitle = available.find((video) => titleKey(cleanTitle(video.title)) === episodeKey);
  if (byTitle) {
    return byTitle;
  }

  const episodeTime = new Date(episode.pubDate).getTime();
  if (Number.isNaN(episodeTime)) {
    return null;
  }
  let closest: YouTubeVideo | null = null;
  let closestGap = MATCH_WINDOW_MS;
  for (const video of available) {
    const gap = Math.abs(new Date(video.publishedAt).getTime() - episodeTime);
    if (gap <= closestGap && titleOverlap(episode.title, video.title)) {
      closest = video;
      closestGap = gap;
    }
  }
  return closest;
}

function toVideoEpisode(video: YouTubeVideo): Episode {
  const durationSeconds = parseIsoDuration(video.duration);
  return {
    id: `yt:${video.id}`,
    kind: "video",
    number: parseEpisodeNumber(video.title),
    title: cleanTitle(video.title),
    link: watchUrl(video.id),
    audioUrl: "",
    pubDate: video.publishedAt,
    publishedLabel: formatPublished(video.publishedAt),
    durationLabel: formatDuration(durationSeconds),
    durationSeconds,
    image: video.thumbnail,
    category: inferCategory(video.title),
    summary: video.description,
    youtubeId: video.id,
    videoUrl: watchUrl(video.id),
    isShort: isShortMedia("video", durationSeconds, video.title),
  };
}

function parseIsoDuration(iso: string | undefined): number {
  if (!iso) {
    return 0;
  }
  const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) {
    return 0;
  }
  const [, hours, minutes, seconds] = match;
  return Number(hours ?? 0) * 3600 + Number(minutes ?? 0) * 60 + Number(seconds ?? 0);
}

function watchUrl(id: string): string {
  return `https://www.youtube.com/watch?v=${id}`;
}

function titleKey(title: string): string {
  return title
    .toLowerCase()
    .replace(/#\s*\d+/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function titleOverlap(a: string, b: string): boolean {
  const wordsA = new Set(titleKey(a).split(" ").filter((word) => word.length > 3));
  if (wordsA.size === 0) {
    return false;
  }
  const wordsB = titleKey(b).split(" ");
  let shared = 0;
  for (const word of wordsB) {
    if (wordsA.has(word)) {
      shared += 1;
    }
  }
  return shared / wordsA.size >= 0.5;
}
