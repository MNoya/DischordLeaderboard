import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  base: "/",
  plugins: [react()],
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
});
