import { Routes, Route, Navigate } from "react-router-dom";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import { PlayerPage } from "./pages/PlayerPage";
import { ArchetypePage } from "./pages/ArchetypePage";

// Hash-based routing per spec — works from any static host.
//
//   #/                       → leaderboard for the active set
//   #/SOS                    → leaderboard for SOS
//   #/SOS/player/chonce      → player profile (set-scoped)
//   #/player/chonce          → player profile, defaults to active set
//   #/archetypes             → archetype board for active set
//   #/SOS/archetypes/WR      → archetype board, set+archetype scoped
//
// Set codes are matched as 2–4 uppercase letters (matches `public_sets.code`).

export function App() {
  return (
    <Routes>
      <Route path="/" element={<LeaderboardPage />} />
      <Route path="/archetypes" element={<ArchetypePage />} />
      <Route path="/archetypes/:archetype" element={<ArchetypePage />} />
      <Route path="/player/:slug" element={<PlayerPage />} />
      <Route path="/players" element={<Navigate to="/" replace />} />

      <Route path="/:setCode" element={<LeaderboardPage />} />
      <Route path="/:setCode/archetypes" element={<ArchetypePage />} />
      <Route path="/:setCode/archetypes/:archetype" element={<ArchetypePage />} />
      <Route path="/:setCode/player/:slug" element={<PlayerPage />} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
