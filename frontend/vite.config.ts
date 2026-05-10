import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import type { Connect } from "vite";

// Spec §14: vite base is `/leaderboard/` so the future LLU subpath already matches.
// Build output goes to `dist/leaderboard/` so the on-disk path mirrors the URL —
// Cloudflare Workers Assets serves files relative to its assets directory, and
// putting dist/leaderboard/index.html lets `/leaderboard` resolve directly.

// Mirror production's no-trailing-slash routing in dev. With `base: "/leaderboard/"`,
// Vite shows a "did you mean to visit /leaderboard/" warning when the URL has no
// slash. We rewrite the request URL internally before Vite's HTML handler runs,
// so the browser bar keeps `/leaderboard` and Vite still serves the SPA.
const noTrailingSlashPlugin = {
  name: "leaderboard-no-trailing-slash",
  configureServer(server: { middlewares: Connect.Server }) {
    server.middlewares.use((req, _res, next) => {
      if (req.url === "/leaderboard" || req.url === "/leaderboard?") {
        req.url = "/leaderboard/";
      } else if (req.url?.startsWith("/leaderboard?")) {
        req.url = "/leaderboard/" + req.url.slice("/leaderboard".length);
      }
      next();
    });
  },
};

// CF Pages reads _redirects from the deployment root (dist/), not from
// dist/leaderboard/ where Vite's public/ files land because of base "/leaderboard/".
const emitRootRedirectsPlugin = {
  name: "emit-root-redirects",
  apply: "build" as const,
  closeBundle() {
    const dest = path.resolve(__dirname, "dist/_redirects");
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, "/leaderboard/*  /leaderboard/index.html  200\n");
  },
};

export default defineConfig({
  base: "/leaderboard/",
  plugins: [react(), noTrailingSlashPlugin, emitRootRedirectsPlugin],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: "dist/leaderboard",
    emptyOutDir: true,
  },
  server: { port: 5173 },
});
