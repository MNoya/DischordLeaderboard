import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Spec §14: vite base is `/leaderboard/` so the future LLU subpath already matches.
export default defineConfig({
  base: "/leaderboard/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: { port: 5173 },
});
