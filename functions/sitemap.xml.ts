// Generated sitemap for the indexable pages. Static marketing/content routes plus
// one entry per set (leaderboard, episodes) and per episode category. Set lists come
// from the public views so a rotation or a fresh back-catalog sync shows up without a
// redeploy. Episode set pages list only sets that actually have episodes, so the
// sitemap never advertises an empty grid.

import {
  PUBLIC_SUPABASE_URL,
  PUBLIC_SUPABASE_PUBLISHABLE_KEY,
} from "../frontend/src/data/public-supabase-config";
import { EPISODE_CATEGORIES, categorySlug } from "../frontend/src/data/episodes";

const restGet = (query: string): Promise<Response> =>
  fetch(`${PUBLIC_SUPABASE_URL}/rest/v1/${query}`, {
    headers: {
      apikey: PUBLIC_SUPABASE_PUBLISHABLE_KEY,
      authorization: `Bearer ${PUBLIC_SUPABASE_PUBLISHABLE_KEY}`,
    },
    cf: { cacheTtl: 3600, cacheEverything: true },
  });

const fetchSetCodes = async (): Promise<string[]> => {
  try {
    const resp = await restGet("public_sets?select=code");
    if (!resp.ok) return [];
    const rows = (await resp.json()) as Array<{ code: string }>;
    return rows.map((r) => r.code.toUpperCase());
  } catch {
    return [];
  }
};

const fetchEpisodeSetCodes = async (): Promise<string[]> => {
  try {
    const resp = await restGet("public_episodes?select=set_code");
    if (!resp.ok) return [];
    const rows = (await resp.json()) as Array<{ set_code: string | null }>;
    const codes = new Set<string>();
    for (const row of rows) {
      if (row.set_code) codes.add(row.set_code.toUpperCase());
    }
    return [...codes];
  } catch {
    return [];
  }
};

export const onRequest: PagesFunction = async (context) => {
  const origin = new URL(context.request.url).origin;
  const [setCodes, episodeSetCodes] = await Promise.all([fetchSetCodes(), fetchEpisodeSetCodes()]);

  const paths = ["/", "/leaderboard", "/leaderboard/about", "/episodes", "/tier-list", "/community"];
  for (const code of setCodes) {
    paths.push(`/leaderboard/${code}`);
  }
  for (const category of EPISODE_CATEGORIES) {
    paths.push(`/episodes/${categorySlug(category)}`);
  }
  for (const code of episodeSetCodes) {
    paths.push(`/episodes/${code.toLowerCase()}`);
  }

  const urls = paths.map((path) => `  <url><loc>${origin}${path}</loc></url>`).join("\n");
  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>
`;

  return new Response(body, {
    headers: {
      "content-type": "application/xml; charset=utf-8",
      "cache-control": "public, max-age=3600",
    },
  });
};
