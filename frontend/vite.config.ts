import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    base: "/",
    plugins: [react(), youtubeDevApi(env.YOUTUBE_API_KEY)],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      proxy: {
        "/api/tier-list": {
          target: "https://www.17lands.com",
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api\/tier-list/, "/data/tier_list"),
        },
      },
    },
  };
});

const CHANNEL_HANDLE = "limitedlevel-ups";
const YOUTUBE_API = "https://www.googleapis.com/youtube/v3";

function youtubeDevApi(key: string | undefined): Plugin {
  return {
    name: "youtube-dev-api",
    configureServer(server) {
      server.middlewares.use("/api/youtube", async (_req, res) => {
        res.setHeader("content-type", "application/json");
        if (!key) {
          res.statusCode = 500;
          res.end(JSON.stringify({ error: "Set YOUTUBE_API_KEY in frontend/.env to use /api/youtube in dev" }));
          return;
        }
        try {
          const videos = await fetchUploads(key);
          res.end(JSON.stringify({ videos }));
        } catch (error) {
          res.statusCode = 502;
          res.end(JSON.stringify({ error: String(error) }));
        }
      });
    },
  };
}

async function fetchUploads(key: string) {
  const channelUrl = `${YOUTUBE_API}/channels?part=contentDetails&forHandle=${CHANNEL_HANDLE}&key=${key}`;
  const channelRes = await fetch(channelUrl);
  const channelJson = await channelRes.json();
  const uploads = channelJson?.items?.[0]?.contentDetails?.relatedPlaylists?.uploads;
  if (!uploads) {
    throw new Error("Could not resolve uploads playlist");
  }

  const videos: Array<Record<string, string>> = [];
  let pageToken = "";
  for (let page = 0; page < 10; page += 1) {
    const url =
      `${YOUTUBE_API}/playlistItems?part=snippet&maxResults=50&playlistId=${uploads}&key=${key}` +
      (pageToken ? `&pageToken=${pageToken}` : "");
    const res = await fetch(url);
    const json = await res.json();
    for (const item of json.items ?? []) {
      const snippet = item.snippet ?? {};
      const videoId = snippet.resourceId?.videoId;
      const title = snippet.title ?? "";
      if (!videoId || title === "Private video" || title === "Deleted video") {
        continue;
      }
      const thumbs = snippet.thumbnails ?? {};
      const best = thumbs.maxres ?? thumbs.standard ?? thumbs.high ?? thumbs.medium ?? thumbs.default;
      videos.push({
        id: videoId,
        title,
        publishedAt: snippet.publishedAt ?? "",
        description: snippet.description ?? "",
        thumbnail: best?.url ?? "",
      });
    }
    if (!json.nextPageToken) {
      break;
    }
    pageToken = json.nextPageToken;
  }
  return videos;
}
