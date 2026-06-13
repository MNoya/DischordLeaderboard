// Podcast episodes pulled live from the Libsyn RSS feed (CORS-open, fetched
// browser-direct like the Supabase reads). Parsed with DOMParser; category is
// inferred from the title since Libsyn carries no per-episode taxonomy.

export const LIBSYN_FEED_URL = "https://feeds.libsyn.com/limitedlevelups/rss";

export const EPISODE_CATEGORIES = [
  "Set Primer",
  "Set Review",
  "Draft-along",
  "Sunset",
  "Q&A",
  "Strategy",
] as const;

export type EpisodeCategory = (typeof EPISODE_CATEGORIES)[number];

export type MediaKind = "episode" | "video";

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
    };
  });
}

const CATEGORY_KEYWORDS: Array<[EpisodeCategory, RegExp]> = [
  ["Set Primer", /primer|first impressions|first look/i],
  ["Sunset", /sunset|send-?off|goodbye|state of the format|farewell|wrap-?up/i],
  ["Q&A", /mailbag|q&a|listener|questions/i],
  ["Draft-along", /draft-?along|draft log|live draft|drafting with/i],
  ["Set Review", /set review|ranking|tier list|best|underrated|overrated|commons|uncommons|rares|mythics|cards/i],
];

export function inferCategory(title: string): EpisodeCategory {
  for (const [category, pattern] of CATEGORY_KEYWORDS) {
    if (pattern.test(title)) {
      return category;
    }
  }
  return "Strategy";
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
