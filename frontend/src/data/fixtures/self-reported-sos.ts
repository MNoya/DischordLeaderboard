import type { SelfReportedTrophyTally } from "../selfReported";

// SOS self-reported trophies (paper/MTGO runs logged via /trophy). Never scored — they lift the
// trophy count only. mull2five has no 17lands data, so enters the board at score 0 yet tops the
// trophy sort; lark and dado already rank on scored play and get their tallies added on top.
export const selfReportedTrophiesSosFixture: SelfReportedTrophyTally[] = [
  { slug: "mull2five", displayName: "mull2five", avatarUrl: null, trophies: 41 },
  { slug: "paperjack", displayName: "paperjack", avatarUrl: null, trophies: 7 },
  { slug: "lark", displayName: "Lark", avatarUrl: null, trophies: 4 },
  { slug: "dado", displayName: "dado", avatarUrl: null, trophies: 3 },
];
