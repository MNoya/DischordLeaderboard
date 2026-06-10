export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);

  const response = await context.next();
  if (response.status !== 404) return response;
  if (context.request.method !== "GET") return response;

  const lastSegment = url.pathname.split("/").pop() ?? "";
  if (lastSegment.includes(".")) return response;

  const indexUrl = new URL("/index.html", url.origin);
  const indexResp = await context.env.ASSETS.fetch(indexUrl.toString());
  const headers = new Headers(indexResp.headers);
  headers.set("Cache-Control", "public, max-age=0, must-revalidate");
  return new Response(indexResp.body, { status: 200, headers });
};
