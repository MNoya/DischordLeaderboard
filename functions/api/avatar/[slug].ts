// Discord won't render a cdn.discordapp.com og:image in a link preview, so player-profile
// unfurls point og:image here and we stream the avatar back from our own origin. Falls back
// to the LLU logo for players with no avatar (e.g. pod-only players).
import {
  PUBLIC_SUPABASE_URL,
  PUBLIC_SUPABASE_PUBLISHABLE_KEY,
} from "../../../frontend/src/data/public-supabase-config";

const upsizeAvatar = (url: string): string => url.replace(/([?&]size=)\d+/, "$1512");

const fetchAvatarUrl = async (slug: string): Promise<string | null> => {
  try {
    const resp = await fetch(
      `${PUBLIC_SUPABASE_URL}/rest/v1/public_leaderboard?slug=eq.${encodeURIComponent(slug)}&select=avatar_url&limit=1`,
      {
        headers: {
          apikey: PUBLIC_SUPABASE_PUBLISHABLE_KEY,
          authorization: `Bearer ${PUBLIC_SUPABASE_PUBLISHABLE_KEY}`,
        },
        cf: { cacheTtl: 600, cacheEverything: true },
      },
    );
    if (resp.ok) {
      const rows = (await resp.json()) as Array<{ avatar_url: string | null }>;
      if (rows[0]?.avatar_url) return upsizeAvatar(rows[0].avatar_url);
    }
  } catch {
    // fall through to the logo
  }
  return null;
};

export const onRequest: PagesFunction = async (context) => {
  const slug = String(context.params.slug ?? "").replace(/\.png$/, "");
  const origin = new URL(context.request.url).origin;
  const logo = `${origin}/llu-logo.png`;

  const avatar = await fetchAvatarUrl(slug);
  const fetchOpts = { cf: { cacheTtl: 86400, cacheEverything: true } };
  let image = await fetch(avatar ?? logo, fetchOpts);
  if (!image.ok && avatar) {
    image = await fetch(logo, fetchOpts);
  }

  const headers = new Headers();
  headers.set("Content-Type", image.headers.get("Content-Type") ?? "image/png");
  headers.set("Cache-Control", "public, max-age=86400");
  return new Response(image.body, { status: 200, headers });
};
