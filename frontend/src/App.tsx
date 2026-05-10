import { Routes, Route, Navigate } from "react-router-dom";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { PlayerPage } from "./pages/PlayerPage";
import { AboutPage } from "./pages/AboutPage";

// Browser routes per spec, basename "/leaderboard" applied at the BrowserRouter.
//
//   /                       → leaderboard for the active set
//   /SOS                    → leaderboard for SOS
//   /SOS/player/chonce      → player profile (set-scoped)
//   /player/chonce          → player profile, defaults to active set
//
// Archetype scoping happens via the inline picker on the leaderboard page,
// not as a separate route. Set codes are 2–4 uppercase letters.

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LeaderboardPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/player/:slug" element={<PlayerPage />} />
      <Route path="/players" element={<Navigate to="/" replace />} />

      <Route path="/:setCode" element={<LeaderboardPage />} />
      <Route path="/:setCode/player/:slug" element={<PlayerPage />} />

      {/* Legacy archetype routes redirect to the home leaderboard — the
          archetype picker now lives there inline. */}
      <Route path="/archetypes/*" element={<Navigate to="/" replace />} />
      <Route path="/:setCode/archetypes/*" element={<Navigate to="/" replace />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
