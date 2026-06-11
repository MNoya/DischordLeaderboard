import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { Provider as TooltipProvider } from "@radix-ui/react-tooltip";
import { ScoringModalHost } from "./components/ScoringModal";
import { HomePage } from "./pages/HomePage";
import { EpisodesPage } from "./pages/EpisodesPage";
import { CommunityPage } from "./pages/CommunityPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { PlayerPage } from "./pages/PlayerPage";
import { PodDraftsPage, PodsRoute } from "./pages/PodDraftsPage";
import { AboutPage } from "./pages/AboutPage";
import { TierListPage } from "./pages/TierListPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { preloadGuildLogos } from "./data/guild-art";

// Browser routes. The leaderboard is one section of the site, mounted at the
// lowercase /leaderboard; set codes stay uppercase under it.
//
//   /                          → redirect to /leaderboard
//   /leaderboard               → leaderboard for the active set
//   /leaderboard/SOS           → leaderboard for SOS
//   /leaderboard/SOS/player/x  → player profile (set-scoped)
//   /leaderboard/player/x      → player profile, defaults to active set
//
// Archetype scoping happens via the inline picker on the leaderboard page,
// not as a separate route. Set codes are 2–4 uppercase letters.

export function App() {
  useEffect(() => {
    preloadGuildLogos();
  }, []);
  return (
    <TooltipProvider delayDuration={150} skipDelayDuration={0} disableHoverableContent>
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/episodes" element={<EpisodesPage />} />
      <Route path="/community" element={<CommunityPage />} />

      <Route path="/leaderboard" element={<LeaderboardPage />} />
      <Route path="/leaderboard/player/:slug" element={<PlayerPage />} />
      <Route path="/leaderboard/:setCode" element={<LeaderboardPage />} />
      <Route path="/leaderboard/:setCode/player/:slug" element={<PlayerPage />} />

      <Route path="/about" element={<AboutPage />} />
      <Route path="/players" element={<Navigate to="/leaderboard" replace />} />

      <Route path="/pods" element={<PodDraftsPage />} />
      <Route path="/pods/:slug" element={<PodsRoute />} />

      <Route path="/tier-list" element={<TierListPage />} />
      <Route path="/tier-list/:setCode" element={<TierListPage />} />

      {/* Legacy archetype routes redirect to the leaderboard — the archetype
          picker now lives there inline. */}
      <Route path="/leaderboard/archetypes/*" element={<Navigate to="/leaderboard" replace />} />
      <Route path="/leaderboard/:setCode/archetypes/*" element={<Navigate to="/leaderboard" replace />} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
    <ScoringModalHost />
    </TooltipProvider>
  );
}
