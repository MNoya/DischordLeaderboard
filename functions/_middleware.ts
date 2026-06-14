// Serves the SPA index.html for every HTML route and rewrites its <head> meta per
// route so link unfurls (Discord, Twitter, Slack) reflect the page instead of the
// single baked-in preview. Crawlers don't run JS, so this is the only place per-page
// titles, descriptions, and thumbnails can land.
//
// Embed title and browser tab title diverge on purpose. The embed carries the brand in
// the gray og:site_name line, so og:title is the bare label (e.g. "MSH Leaderboard",
// "Noya · Player Profile"). The tab has no gray line, so <title> appends the brand:
// "MSH Leaderboard | Limited Level-Ups". Home is the exception: no gray line, the brand
// is the title. DocumentTitle reproduces the tab title client-side on SPA navigation.
//
// Thumbnail per route: a player's Discord avatar (falling back to the baked LLU logo
// when they have none), a set's white symbol on set routes, the LLU logo everywhere else.

import {
  PUBLIC_SUPABASE_URL,
  PUBLIC_SUPABASE_PUBLISHABLE_KEY,
} from "../frontend/src/data/public-supabase-config";
import { SITE_NAME as SITE, TITLE_SEPARATOR, TIER_LIST_PREVIEW_SETS } from "../frontend/src/data/constants";

const LEADERBOARD_DESCRIPTION =
  "Check ranks and trophies from the community. /join on Discord to share your drafts and climb the leaderboard";
const HOME_DESCRIPTION = "Weekly episodes, set reviews, strategy, and community events. Join the Discord and climb the leaderboard.";

type ImageIntent = { kind: "url"; url: string } | { kind: "setSymbol"; code: string } | null;

type RouteMeta = {
  ogTitle: string;
  tabTitle: string;
  siteName: string | null;
  description: string | null;
  image: ImageIntent;
};

const page = (label: string, description: string | null, image: ImageIntent = null): RouteMeta => ({
  ogTitle: label,
  tabTitle: `${label}${TITLE_SEPARATOR}${SITE}`,
  siteName: SITE,
  description,
  image,
});

const HOME_META: RouteMeta = { ogTitle: SITE, tabTitle: SITE, siteName: null, description: HOME_DESCRIPTION, image: null };

const slugToName = (slug: string): string => slug.replace(/-/g, " ");

const titleCaseSlug = (slug: string, setCodes: Set<string>): string =>
  slug
    .split("-")
    .map((word) => {
      const upper = word.toUpperCase();
      if (setCodes.has(upper)) return upper;
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");

const restGet = (query: string): Promise<Response> =>
  fetch(`${PUBLIC_SUPABASE_URL}/rest/v1/${query}`, {
    headers: {
      apikey: PUBLIC_SUPABASE_PUBLISHABLE_KEY,
      authorization: `Bearer ${PUBLIC_SUPABASE_PUBLISHABLE_KEY}`,
    },
    cf: { cacheTtl: 600, cacheEverything: true },
  });

const fetchSetCodes = async (): Promise<Set<string>> => {
  try {
    const resp = await restGet("public_sets?select=code");
    if (!resp.ok) return new Set();
    const rows = (await resp.json()) as Array<{ code: string }>;
    return new Set(rows.map((r) => r.code.toUpperCase()));
  } catch {
    return new Set();
  }
};

const fetchSetName = async (code: string): Promise<string> => {
  try {
    const resp = await restGet(`public_sets?code=eq.${encodeURIComponent(code)}&select=name&limit=1`);
    if (resp.ok) {
      const rows = (await resp.json()) as Array<{ name: string }>;
      if (rows[0]?.name) return rows[0].name;
    }
  } catch {
    // fall through
  }
  return TIER_LIST_PREVIEW_SETS[code]?.name ?? code;
};

type PlayerCard = { name: string; avatarUrl: string | null };

const fetchPlayer = async (slug: string): Promise<PlayerCard> => {
  try {
    const resp = await restGet(
      `public_leaderboard?slug=eq.${encodeURIComponent(slug)}&select=display_name,avatar_url&limit=1`,
    );
    if (resp.ok) {
      const rows = (await resp.json()) as Array<{ display_name: string; avatar_url: string | null }>;
      if (rows[0]?.display_name) {
        return { name: rows[0].display_name, avatarUrl: rows[0].avatar_url ?? null };
      }
    }
  } catch {
    // fall through to the slug
  }
  return { name: slugToName(slug), avatarUrl: null };
};

const playerMeta = (player: PlayerCard): RouteMeta => ({
  ogTitle: `${player.name} · Player Profile`,
  tabTitle: `${player.name}${TITLE_SEPARATOR}${SITE}`,
  siteName: SITE,
  description: `Check ${player.name}'s drafts & stats on the leaderboard.`,
  image: player.avatarUrl ? { kind: "url", url: player.avatarUrl } : null,
});

const resolveMeta = async (pathname: string): Promise<RouteMeta> => {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) {
    return HOME_META;
  }
  const [section, ...rest] = segments;

  if (section === "leaderboard") {
    if (rest.length === 0) {
      return page("Leaderboard", LEADERBOARD_DESCRIPTION);
    }
    if (rest[0] === "about") {
      return page("About", "Learn how the community leaderboard works.");
    }
    if (rest[0] === "player" && rest[1]) {
      return playerMeta(await fetchPlayer(rest[1]));
    }
    const setCode = rest[0].toUpperCase();
    if (rest[1] === "player" && rest[2]) {
      return playerMeta(await fetchPlayer(rest[2]));
    }
    const setName = await fetchSetName(setCode);
    return page(
      `${setCode} Leaderboard`,
      `Check ${setName} ranks and trophies on the leaderboard.`,
      { kind: "setSymbol", code: setCode },
    );
  }

  if (section === "tier-list") {
    if (rest[0]) {
      const setCode = rest[0].toUpperCase();
      const setName = await fetchSetName(setCode);
      return page(
        `${setCode} Tier List`,
        `Check updated Set Review grades for ${setName}.`,
        { kind: "setSymbol", code: setCode },
      );
    }
    return page("Tier List", "Check updated Set Review grades for every set.");
  }

  if (section === "pods") {
    if (rest[0]) {
      const setCodes = await fetchSetCodes();
      return page(titleCaseSlug(rest[0], setCodes), "Check seats, logs & replays for this pod draft.");
    }
    return page("Pod Drafts", "Check community pod draft results and standings.");
  }

  if (section === "p0p1") {
    return page("Pack 0, Pick 1", "Pick a team of the cards you think will perform best from the upcoming set.");
  }
  if (section === "episodes") {
    return page("Episodes", "Check out the latest episodes, or search the archive.");
  }
  if (section === "community") {
    return page("Community", "Check out the Discord and start drafting.");
  }
  if (section === "about") {
    return page("About", "Learn how the community leaderboard works.");
  }

  return { ...HOME_META, description: null };
};

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  if (context.request.method !== "GET") return context.next();

  const lastSegment = url.pathname.split("/").pop() ?? "";
  if (lastSegment.includes(".") || url.pathname.startsWith("/api/")) return context.next();

  const indexUrl = new URL("/index.html", url.origin);
  const indexResp = await context.env.ASSETS.fetch(indexUrl.toString());

  const meta = await resolveMeta(url.pathname);
  const ogUrl = `${url.origin}${url.pathname}`;
  const imageUrl = await resolveImageUrl(meta.image, url.origin, context.env.ASSETS);

  const setContent = (value: string): HTMLRewriterElementContentHandlers => ({
    element: (el) => el.setAttribute("content", value),
  });
  const remove: HTMLRewriterElementContentHandlers = { element: (el) => el.remove() };

  const descriptionHandler = meta.description === null ? remove : setContent(meta.description);
  const siteNameHandler = meta.siteName === null ? remove : setContent(meta.siteName);

  const headers = new Headers(indexResp.headers);
  headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  const baseResponse = new Response(indexResp.body, { status: 200, headers });

  let rewriter = new HTMLRewriter()
    .on("title", { element: (el) => el.setInnerContent(meta.tabTitle) })
    .on('meta[property="og:site_name"]', siteNameHandler)
    .on('meta[property="og:title"]', setContent(meta.ogTitle))
    .on('meta[name="twitter:title"]', setContent(meta.ogTitle))
    .on('meta[property="og:url"]', setContent(ogUrl))
    .on('meta[name="description"]', descriptionHandler)
    .on('meta[property="og:description"]', descriptionHandler)
    .on('meta[name="twitter:description"]', descriptionHandler);

  if (imageUrl) {
    rewriter = rewriter
      .on('meta[property="og:image"]', setContent(imageUrl))
      .on('meta[name="twitter:image"]', setContent(imageUrl))
      .on('meta[property="og:image:width"]', remove)
      .on('meta[property="og:image:height"]', remove)
      .on('meta[property="og:image:alt"]', setContent(meta.ogTitle));
  }

  return rewriter.transform(baseResponse);
};

const resolveImageUrl = async (image: ImageIntent, origin: string, assets: Fetcher): Promise<string | null> => {
  if (image === null) return null;
  if (image.kind === "url") return image.url;
  const candidate = `${origin}/set-symbols/${image.code.toLowerCase()}.png`;
  try {
    const resp = await assets.fetch(candidate);
    return resp.ok ? candidate : null;
  } catch {
    return null;
  }
};
