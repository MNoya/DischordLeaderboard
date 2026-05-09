// Selects the data backend at module-load time. If VITE_SUPABASE_URL +
// VITE_SUPABASE_ANON_KEY are set, real Supabase fetchers are used; otherwise
// the fixture-backed mock API runs. The hook layer imports from here so it
// never knows which one is live.

import { useSupabase } from "./supabase";

import * as mock from "./mockApi";
import * as real from "./realApi";

const impl = useSupabase ? real : mock;

export const fetchSets = impl.fetchSets;
export const fetchLeaderboard = impl.fetchLeaderboard;
export const fetchFormatLeaderboard = impl.fetchFormatLeaderboard;
export const fetchArchetypeLeaderboard = impl.fetchArchetypeLeaderboard;
export const fetchPlayerProfile = impl.fetchPlayerProfile;
export const fetchPlayerDraftEvents = impl.fetchPlayerDraftEvents;
export const fetchRecentTrophies = impl.fetchRecentTrophies;
