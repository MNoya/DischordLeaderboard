// Server-side passthrough to the MTG Scribe events API. SiteGround's anti-bot
// (/.well-known/sgcaptcha/) challenges datacenter egress IPs with a 202 HTML page,
// so the bot on Railway can't reach mtgscribe.com directly — but a Cloudflare IP
// is served clean JSON. The bot fetches this endpoint instead and keeps its own
// pagination loop; only the listed query params are forwarded to a fixed upstream.

const SCRIBE_EVENTS_URL = "https://mtgscribe.com/wp-json/tribe/events/v1/events";
const FORWARDED_PARAMS = ["start_date", "end_date", "per_page", "page", "_cb"];

export const onRequestGet: PagesFunction = async (context) => {
  const incoming = new URL(context.request.url);
  const upstream = new URL(SCRIBE_EVENTS_URL);
  for (const key of FORWARDED_PARAMS) {
    const value = incoming.searchParams.get(key);
    if (value !== null) {
      upstream.searchParams.set(key, value);
    }
  }

  const response = await fetch(upstream.toString(), {
    headers: { Accept: "application/json" },
    cf: { cacheTtl: 0 },
  });
  const body = await response.text();

  return new Response(body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });
};
