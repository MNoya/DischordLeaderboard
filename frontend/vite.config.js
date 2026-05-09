import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
// Spec §14: vite base is `/leaderboard/` so the future LLU subpath already matches.
// Build output goes to `dist/leaderboard/` so the on-disk path mirrors the URL —
// Cloudflare Workers Assets serves files relative to its assets directory, and
// putting dist/leaderboard/index.html lets `/leaderboard` resolve directly.
export default defineConfig({
    base: "/leaderboard/",
    plugins: [react()],
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
