// Proxies 17lands' dict-shaped tier-list endpoint (card ratings + last_updated),
// which lacks CORS headers and so can't be fetched browser-side. In dev the
// same path is served by a vite proxy entry instead.
export const onRequestGet: PagesFunction = async (context) => {
  const uid = context.params.uid;
  if (typeof uid !== "string" || !/^[0-9a-f]{32}$/.test(uid)) {
    return new Response("Bad uid", { status: 400 });
  }

  const upstream = await fetch(`https://www.17lands.com/data/tier_list/${uid}`, {
    headers: { accept: "application/json" },
    cf: { cacheTtl: 600, cacheEverything: true },
  });
  if (!upstream.ok) {
    return new Response("Upstream error", { status: 502 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "public, max-age=600",
    },
  });
};
