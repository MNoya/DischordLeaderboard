// SPA fallback for Cloudflare Pages.
//
// Pass through to the static asset for the request; if that returns 404 and
// the path is a navigation (no file extension), serve /index.html so React
// Router resolves the route client-side.
export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);

  const response = await context.next();
  if (response.status !== 404) return response;
  if (context.request.method !== "GET") return response;

  const lastSegment = url.pathname.split("/").pop() ?? "";
  if (lastSegment.includes(".")) return response;

  const indexUrl = new URL("/index.html", url.origin);
  const indexResp = await context.env.ASSETS.fetch(indexUrl.toString());
  return new Response(indexResp.body, {
    status: 200,
    headers: indexResp.headers,
  });
};
