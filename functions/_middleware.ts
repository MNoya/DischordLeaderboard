// Serves the SPA index.html for every HTML route and rewrites its <head> meta
// per route so link unfurls (Discord, Twitter, Slack) reflect the shared page
// instead of the single baked-in leaderboard preview. Crawlers don't run JS, so
// this is the only place per-page titles can land.
//
// The og:site_name grey provider line is stripped so cards show only title and
// description; the site name rides in the title instead (page | Limited Level-Ups).
//
// Player titles and pod set codes come from the same cached public_* views the
// site reads, so player capitalization is the real display_name and the set
// code list never drifts from bot/sets.py.

import {
  PUBLIC_SUPABASE_URL,
  PUBLIC_SUPABASE_PUBLISHABLE_KEY,
} from "../frontend/src/data/public-supabase-config";

const SITE = "Limited Level-Ups";
const LEADERBOARD_DESCRIPTION =
  "Check ranks and trophies from the community. /join on Discord to share your drafts";
const HOME_DESCRIPTION =
  "Discuss Limited strategy, keep up with the latest sets, and draft with a community of dedicated players.";

type RouteMeta = { title: string; description: string | null };

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

const playerName = async (slug: string): Promise<string> => {
  try {
    const resp = await restGet(
      `public_leaderboard?slug=eq.${encodeURIComponent(slug)}&select=display_name&limit=1`,
    );
    if (resp.ok) {
      const rows = (await resp.json()) as Array<{ display_name: string }>;
      if (rows[0]?.display_name) return rows[0].display_name;
    }
  } catch {
    // fall through to the slug
  }
  return slugToName(slug);
};

const resolveMeta = async (pathname: string): Promise<RouteMeta> => {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) {
    return { title: SITE, description: HOME_DESCRIPTION };
  }
  const [section, ...rest] = segments;

  if (section === "leaderboard") {
    if (rest.length === 0) {
      return { title: "Leaderboard", description: LEADERBOARD_DESCRIPTION };
    }
    if (rest[0] === "player" && rest[1]) {
      return { title: await playerName(rest[1]), description: null };
    }
    const setCode = rest[0].toUpperCase();
    if (rest[1] === "player" && rest[2]) {
      return { title: `${await playerName(rest[2])} | ${setCode}`, description: null };
    }
    return { title: `${setCode} Leaderboard`, description: null };
  }

  if (section === "tier-list") {
    if (rest[0]) {
      return { title: `${rest[0].toUpperCase()} Tier List`, description: null };
    }
    return { title: "Tier List", description: null };
  }

  if (section === "pods") {
    if (rest[0]) {
      const setCodes = await fetchSetCodes();
      return { title: titleCaseSlug(rest[0], setCodes), description: null };
    }
    return { title: "Pod Drafts", description: null };
  }

  if (section === "episodes") return { title: "Episodes", description: null };
  if (section === "community") return { title: "Community", description: null };
  if (section === "about") return { title: "About", description: null };

  return { title: SITE, description: null };
};

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  if (context.request.method !== "GET") return context.next();

  const lastSegment = url.pathname.split("/").pop() ?? "";
  if (lastSegment.includes(".") || url.pathname.startsWith("/api/")) return context.next();

  const indexUrl = new URL("/index.html", url.origin);
  const indexResp = await context.env.ASSETS.fetch(indexUrl.toString());

  const meta = await resolveMeta(url.pathname);
  const title = meta.title === SITE ? SITE : `${meta.title} | ${SITE}`;
  const ogUrl = `${url.origin}${url.pathname}`;

  const descriptionHandler: HTMLRewriterElementContentHandlers =
    meta.description === null
      ? { element: (el) => el.remove() }
      : { element: (el) => el.setAttribute("content", meta.description as string) };

  const setContent = (value: string): HTMLRewriterElementContentHandlers => ({
    element: (el) => el.setAttribute("content", value),
  });

  const headers = new Headers(indexResp.headers);
  headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  const baseResponse = new Response(indexResp.body, { status: 200, headers });

  return new HTMLRewriter()
    .on("title", { element: (el) => el.setInnerContent(title) })
    .on('meta[property="og:site_name"]', { element: (el) => el.remove() })
    .on('meta[property="og:title"]', setContent(title))
    .on('meta[name="twitter:title"]', setContent(title))
    .on('meta[property="og:url"]', setContent(ogUrl))
    .on('meta[name="description"]', descriptionHandler)
    .on('meta[property="og:description"]', descriptionHandler)
    .on('meta[name="twitter:description"]', descriptionHandler)
    .transform(baseResponse);
};
