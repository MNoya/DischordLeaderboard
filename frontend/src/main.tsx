import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Spec §6 — view-backed reads are cheap; refetch on window focus is noise.
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// BrowserRouter with basename="/leaderboard" gives clean URLs like
// /leaderboard/SOS/player/chonce. Cloudflare Pages serves the SPA index for
// any /leaderboard/* path via the SPA-fallback rewrite in dist/_redirects.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/leaderboard">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
