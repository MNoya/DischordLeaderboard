// Podcast episodes pulled live from the Libsyn RSS feed (CORS-open, fetched
// browser-direct like the Supabase reads). Parsed with DOMParser; category is
// inferred from the title since Libsyn carries no per-episode taxonomy.

export const LIBSYN_FEED_URL = "https://feeds.libsyn.com/limitedlevelups/rss";

export const EPISODE_CATEGORIES = [
  "First Impressions",
  "Set Review",
  "Draft",
  "Metagame",
  "Evergreen",
] as const;

export type EpisodeCategory = (typeof EPISODE_CATEGORIES)[number];

export type MediaKind = "episode" | "video";

// The set bucket for content not tied to any release — general limited skills, draft coaching,
// Top 10s. The bot tags these EVG; live overlay items with no set fall here too.
export const EVERGREEN_SET = { code: "EVG", name: "Evergreen" } as const;

// YouTube Shorts are vertical, ≤3min. This channel's cluster at ≤90s; longer ones (up to 3min)
// are Shorts only when the title carries the hashtag run ("#draft #mtg") that long-form lacks.
const SHORT_MAX_SECONDS = 90;
const SHORT_HASHTAG_MAX_SECONDS = 180;
const SHORT_HASHTAG = /#\w/;

export function isShortMedia(kind: MediaKind, durationSeconds: number, title: string): boolean {
  if (kind !== "video" || durationSeconds <= 0) {
    return false;
  }
  if (durationSeconds <= SHORT_MAX_SECONDS) {
    return true;
  }
  return durationSeconds <= SHORT_HASHTAG_MAX_SECONDS && SHORT_HASHTAG.test(title);
}

export interface Episode {
  id: string;
  kind: MediaKind;
  number: number | null;
  title: string;
  link: string;
  audioUrl: string;
  pubDate: string;
  publishedLabel: string;
  durationLabel: string;
  durationSeconds: number;
  image: string;
  category: EpisodeCategory;
  summary: string;
  youtubeId?: string;
  videoUrl?: string;
  setCode?: string | null;
  setName?: string | null;
  setReleasedAt?: string | null;
  isShort: boolean;
}

export async function fetchEpisodes(): Promise<Episode[]> {
  const res = await fetch(LIBSYN_FEED_URL);
  if (!res.ok) {
    throw new Error(`Libsyn feed responded ${res.status}`);
  }
  const xml = new DOMParser().parseFromString(await res.text(), "application/xml");
  if (xml.querySelector("parsererror")) {
    throw new Error("Could not parse the Libsyn feed");
  }

  return Array.from(xml.querySelectorAll("item")).map((item) => {
    const rawTitle = text(item, "title");
    const durationSeconds = parseDurationSeconds(tagText(item, "itunes:duration"));
    const pubDate = text(item, "pubDate");
    return {
      id: text(item, "guid") || item.querySelector("enclosure")?.getAttribute("url") || rawTitle,
      kind: "episode" as const,
      number: parseEpisodeNumber(rawTitle),
      title: cleanTitle(rawTitle),
      link: text(item, "link"),
      audioUrl: item.querySelector("enclosure")?.getAttribute("url") ?? "",
      pubDate,
      publishedLabel: formatPublished(pubDate),
      durationLabel: formatDuration(durationSeconds),
      durationSeconds,
      image: tagHref(item, "itunes:image"),
      category: inferCategory(rawTitle),
      summary: stripHtml(tagText(item, "itunes:summary") || text(item, "description")),
      isShort: false,
    };
  });
}

const CATEGORY_KEYWORDS: Array<[EpisodeCategory, RegExp]> = [
  ["First Impressions", /primer|first impressions|first look/i],
  ["Metagame", /state of the format|format address|format update|metagame|meta update|mid-?format|what we got wrong|late format/i],
  ["Draft", /draft-?along|draft log|live draft|drafting with/i],
  ["Set Review", /set review|ranking|tier list|best|underrated|overrated|commons|uncommons|rares|mythics|cards/i],
];

export function inferCategory(title: string): EpisodeCategory {
  for (const [category, pattern] of CATEGORY_KEYWORDS) {
    if (pattern.test(title)) {
      return category;
    }
  }
  return "Evergreen";
}

export function parseEpisodeNumber(title: string): number | null {
  const match = title.match(/#\s*(\d+)/);
  return match ? Number(match[1]) : null;
}

export function cleanTitle(title: string): string {
  return title.replace(/^(?:llu|limited level-?ups)\s*#?\s*\d+\s*[:\-–]\s*/i, "").trim() || title;
}

function parseDurationSeconds(raw: string): number {
  if (!raw) {
    return 0;
  }
  if (!raw.includes(":")) {
    return Number(raw) || 0;
  }
  return raw
    .split(":")
    .map(Number)
    .reduce((acc, part) => acc * 60 + (part || 0), 0);
}

export function formatDuration(seconds: number): string {
  if (!seconds) {
    return "";
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return hours ? `${hours}h ${minutes}m` : `${minutes}m`;
}

export function formatPublished(pubDate: string): string {
  const date = new Date(pubDate);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function stripHtml(value: string): string {
  return value.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
}

function text(scope: Element | Document, tag: string): string {
  return scope.querySelector(tag)?.textContent?.trim() ?? "";
}

function tagText(item: Element, qualifiedName: string): string {
  return item.getElementsByTagName(qualifiedName)[0]?.textContent?.trim() ?? "";
}

function tagHref(item: Element, qualifiedName: string): string {
  return item.getElementsByTagName(qualifiedName)[0]?.getAttribute("href")?.trim() ?? "";
}

export interface DbEpisodeRow {
  guid: string;
  kind: MediaKind;
  number: number | null;
  title: string;
  link: string;
  summary: string | null;
  image: string | null;
  published_at: string;
  duration_seconds: number;
  audio_url: string | null;
  youtube_id: string | null;
  category: string;
  set_code: string | null;
  set_name: string | null;
  set_released_at: string | null;
}

// Authoritative episode rows from the public_episodes view, already categorized and
// set-tagged by the bot's playlist sync. Keyed on guid so the live RSS/YouTube overlay
// can dedupe against them by the same id.
export function adaptDbEpisode(row: DbEpisodeRow): Episode {
  return {
    id: row.guid,
    kind: row.kind,
    number: row.number,
    title: row.title,
    link: row.link,
    audioUrl: row.audio_url ?? "",
    pubDate: row.published_at,
    publishedLabel: formatPublished(row.published_at),
    durationLabel: formatDuration(row.duration_seconds),
    durationSeconds: row.duration_seconds,
    image: row.image ?? "",
    category: row.category as EpisodeCategory,
    summary: row.summary ?? "",
    youtubeId: row.youtube_id ?? undefined,
    videoUrl: row.youtube_id ? `https://www.youtube.com/watch?v=${row.youtube_id}` : undefined,
    setCode: row.set_code,
    setName: row.set_name,
    setReleasedAt: row.set_released_at,
    isShort: isShortMedia(row.kind, row.duration_seconds, row.title),
  };
}
