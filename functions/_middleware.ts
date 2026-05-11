// SPA fallback for Cloudflare Pages.
//
// Pass through to the static asset for the request; if that returns 404 and
// the path is a navigation (no file extension) under /leaderboard/, serve
// /leaderboard/index.html so React Router resolves the route client-side.
export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);

  // Root has no static asset (Vite base is /leaderboard/); send visitors to the app
  if (url.pathname === "/") {
    return Response.redirect(new URL("/leaderboard/", url.origin).toString(), 301);
  }

  const response = await context.next();
  if (response.status !== 404) return response;
  if (context.request.method !== "GET") return response;

  if (!url.pathname.startsWith("/leaderboard")) return response;

  const lastSegment = url.pathname.split("/").pop() ?? "";
  if (lastSegment.includes(".")) return response;

  const indexUrl = new URL("/leaderboard/index.html", url.origin);
  const indexResp = await context.env.ASSETS.fetch(indexUrl.toString());
  return new Response(indexResp.body, {
    status: 200,
    headers: indexResp.headers,
  });
};
