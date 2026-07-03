export interface PodParticipant {
  eventId: string;
  playerId: string;
  slug: string;
  displayName: string;
  deckColors: string;
  deckScreenshotUrl: string | null;
  deckScreenshotCaption: string | null;
  placement: number;
  record: string;
  seatIndex: number;
}

export interface PodMatch {
  eventId: string;
  round: number;
  playerA: string;
  playerB: string;
  winner: string;
  score: string;
  reportedAt: string;
}

export interface PodReplayRow {
  eventId: string;
  eventName: string;
  eventDate: string;
  setCode: string;
  playerId: string;
  playerSlug: string;
  playerDisplayName: string;
  gameId: string;
  link: string;
  gameTime: string;
  won: boolean;
  turns: number | null;
  onPlay: boolean | null;
  inferredRound: number | null;
}

export interface PodEvent {
  id: string;
  name: string;
  slug: string;
  setCode: string;
  date: string;
  formatLabel: string;
  totalRounds: number;
  participants: PodParticipant[];
  matches: PodMatch[];
  replays: PodReplayRow[];
}

const EVENT_ID = "3d101b25-090e-4668-ba0e-c0e7614ba4df";
const EVENT_NAME = "SOS Pod Draft #3";
const EVENT_DATE = "2026-05-14";

const PLAYERS = {
  noya:           { id: "p-noya",           slug: "noya",           displayName: "Noya" },
  wave:           { id: "p-wave",           slug: "waveofshadow",   displayName: "WaveofShadow" },
  elfandor:       { id: "p-elfandor",       slug: "elfandor",       displayName: "Elfandor" },
  flutterdev:     { id: "p-flutterdev",     slug: "flutterdev",     displayName: "flutterdev" },
  oophies:        { id: "p-oophies",        slug: "oophies",        displayName: "Oophies" },
  adoodwithgood:  { id: "p-adoodwithgood",  slug: "adoodwithgood",  displayName: "adoodwithgood" },
  lark:           { id: "p-lark",           slug: "lark",           displayName: "Lark" },
  samp:           { id: "p-samp",           slug: "samp",           displayName: "samp" },
} as const;

export const podSos3Fixture: PodEvent = {
  id: EVENT_ID,
  name: EVENT_NAME,
  slug: "sos-pod-draft-3",
  setCode: "SOS",
  date: EVENT_DATE,
  formatLabel: "Pod Draft · Swiss · 3 Rounds",
  totalRounds: 3,

  participants: [
    { eventId: EVENT_ID, playerId: PLAYERS.noya.id,           slug: "noya",           displayName: "Noya",           deckColors: "WU",  deckScreenshotUrl: mockDeckSvg("NOYA", "WU"),               deckScreenshotCaption: "Pure WU tempo, splash for nothing — went 5 picks deep on counterspells.", placement: 2, record: "2-1", seatIndex: 0 },
    { eventId: EVENT_ID, playerId: PLAYERS.wave.id,           slug: "waveofshadow",   displayName: "WaveofShadow",   deckColors: "UBg",  deckScreenshotUrl: mockDeckSvg("WAVEOFSHADOW", "UBg"),      deckScreenshotCaption: "UB tempo, late green splash for removal.", placement: 1, record: "3-0", seatIndex: 1 },
    { eventId: EVENT_ID, playerId: PLAYERS.elfandor.id,       slug: "elfandor",       displayName: "Elfandor",       deckColors: "WR",   deckScreenshotUrl: mockDeckSvg("ELFANDOR", "WR"),           deckScreenshotCaption: "Classic Boros aggro.", placement: 3, record: "2-1", seatIndex: 2 },
    { eventId: EVENT_ID, playerId: PLAYERS.flutterdev.id,     slug: "flutterdev",     displayName: "flutterdev",     deckColors: "BG",                                              deckScreenshotUrl: null,                                    deckScreenshotCaption: null, placement: 4, record: "1-2", seatIndex: 3 },
    { eventId: EVENT_ID, playerId: PLAYERS.oophies.id,        slug: "oophies",        displayName: "Oophies",        deckColors: "RG",    deckScreenshotUrl: mockDeckSvg("OOPHIES", "RG"),            deckScreenshotCaption: "Gruul stompy, big creatures.", placement: 5, record: "1-2", seatIndex: 4 },
    { eventId: EVENT_ID, playerId: PLAYERS.adoodwithgood.id,  slug: "adoodwithgood",  displayName: "adoodwithgood",  deckColors: "UR",                                              deckScreenshotUrl: null,                                    deckScreenshotCaption: null, placement: 6, record: "1-2", seatIndex: 5 },
    { eventId: EVENT_ID, playerId: PLAYERS.lark.id,           slug: "lark",           displayName: "Lark",           deckColors: "WB",  deckScreenshotUrl: mockDeckSvg("LARK", "WB"),               deckScreenshotCaption: "Orzhov sacrifice, never found the engine.", placement: 7, record: "0-3", seatIndex: 6 },
    { eventId: EVENT_ID, playerId: PLAYERS.samp.id,           slug: "samp",           displayName: "samp",           deckColors: "WG",                                              deckScreenshotUrl: mockDeckSvg("SAMP", "WG"),               deckScreenshotCaption: "Selesnya tokens. Anthem effects everywhere.", placement: 8, record: "2-1", seatIndex: 7 },
  ],

  matches: [
    { eventId: EVENT_ID, round: 1, playerA: "Noya",          playerB: "Elfandor",      winner: "Noya",          score: "2-1", reportedAt: matchReportTime(28) },
    { eventId: EVENT_ID, round: 1, playerA: "WaveofShadow",  playerB: "flutterdev",    winner: "WaveofShadow",  score: "2-0", reportedAt: matchReportTime(15) },
    { eventId: EVENT_ID, round: 1, playerA: "Oophies",       playerB: "adoodwithgood", winner: "Oophies",       score: "2-1", reportedAt: matchReportTime(27) },
    { eventId: EVENT_ID, round: 1, playerA: "samp",          playerB: "Lark",          winner: "samp",          score: "2-0", reportedAt: matchReportTime(22) },

    { eventId: EVENT_ID, round: 2, playerA: "WaveofShadow",  playerB: "Noya",          winner: "WaveofShadow",  score: "2-1", reportedAt: matchReportTime(69) },
    { eventId: EVENT_ID, round: 2, playerA: "samp",          playerB: "Oophies",       winner: "samp",          score: "2-1", reportedAt: matchReportTime(72) },
    { eventId: EVENT_ID, round: 2, playerA: "Elfandor",      playerB: "flutterdev",    winner: "Elfandor",      score: "2-0", reportedAt: matchReportTime(62) },
    { eventId: EVENT_ID, round: 2, playerA: "adoodwithgood", playerB: "Lark",          winner: "adoodwithgood", score: "2-0", reportedAt: matchReportTime(65) },

    { eventId: EVENT_ID, round: 3, playerA: "WaveofShadow",  playerB: "samp",          winner: "WaveofShadow",  score: "2-1", reportedAt: matchReportTime(112) },
    { eventId: EVENT_ID, round: 3, playerA: "Noya",          playerB: "Oophies",       winner: "Noya",          score: "2-0", reportedAt: matchReportTime(104) },
    { eventId: EVENT_ID, round: 3, playerA: "Elfandor",      playerB: "adoodwithgood", winner: "Elfandor",      score: "2-1", reportedAt: matchReportTime(111) },
    { eventId: EVENT_ID, round: 3, playerA: "flutterdev",    playerB: "Lark",          winner: "flutterdev",    score: "2-1", reportedAt: matchReportTime(108) },
  ],

  replays: buildReplays(),
};

function gid(idx: number): string {
  return `0000000000000000000000000000${idx.toString(16).padStart(4, "0")}`.slice(-32);
}

function rep(
  pid: string,
  slug: string,
  display: string,
  i: number,
  isoMinutes: number,
  won: boolean,
  turns: number | null,
  onPlay: boolean | null,
  round: number | null,
): PodReplayRow {
  const gameId = gid(i);
  return {
    eventId: EVENT_ID,
    eventName: EVENT_NAME,
    eventDate: EVENT_DATE,
    setCode: "SOS",
    playerId: pid,
    playerSlug: slug,
    playerDisplayName: display,
    gameId,
    link: `https://www.17lands.com/user/game_replay/20260514/${gameId}/0`,
    gameTime: minutesToIso(isoMinutes),
    won,
    turns,
    onPlay,
    inferredRound: round,
  };
}

function minutesToIso(minsAfter20h: number): string {
  const base = new Date("2026-05-14T20:00:00Z").getTime();
  return new Date(base + minsAfter20h * 60_000).toISOString();
}

function matchReportTime(minsAfter20h: number): string {
  return minutesToIso(minsAfter20h);
}

function mockDeckSvg(name: string, colors: string): string {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 900 600' preserveAspectRatio='xMidYMid slice'>
<rect width='900' height='600' fill='#14181f'/>
<rect x='12' y='12' width='876' height='576' fill='none' stroke='#2a3142' stroke-width='2'/>
<text x='450' y='270' fill='#e6ecf5' font-family='Bebas Neue, sans-serif' font-size='80' text-anchor='middle' letter-spacing='6'>${name}</text>
<text x='450' y='340' fill='#7a8395' font-family='Bebas Neue, sans-serif' font-size='32' text-anchor='middle' letter-spacing='8'>${colors} · SOS POD #3</text>
<text x='450' y='420' fill='#4a5163' font-family='Space Grotesk, sans-serif' font-size='16' text-anchor='middle'>fixture deck screenshot — discord image url in production</text>
</svg>`;
  return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

function buildReplays(): PodReplayRow[] {
  const out: PodReplayRow[] = [];
  let n = 1;

  // Noya: R1 W 2-1 vs Elfandor, R2 L 1-2 vs Wave, R3 W 2-0 vs Oophies
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++,  5, true,  9,  false, 1));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 14, false, 10, true,  1));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 23, true,  12, false, 1));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 47, true,  11, true,  2));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 56, false, 14, false, 2));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 66, false, 8,  false, 2));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++, 92, true,  7,  true,  3));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++,100, true,  13, true,  3));
  out.push(rep(PLAYERS.noya.id, "noya", "Noya", n++,115, true,  9,  false, null));

  // Wave: R1 W 2-0 vs flutter, R2 W 2-1 vs Noya, R3 W 2-1 vs samp
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++,  4, true,  6,  true,  1));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++, 11, true,  8,  false, 1));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++, 45, false, 11, false, 2));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++, 56, true,  14, true,  2));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++, 65, true,  8,  true,  2));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++, 90, true,  13, false, 3));
  out.push(rep(PLAYERS.wave.id, "waveofshadow", "WaveofShadow", n++,108, true,  7,  true,  3));

  // Elfandor: R1 L 1-2 vs Noya, R2 W 2-0 vs flutter, R3 W 2-1 vs adood
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++,  5, false, 9,  true,  1));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++, 14, true,  10, false, 1));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++, 23, false, 12, true,  1));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++, 49, true,  6,  true,  2));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++, 58, true,  11, false, 2));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++, 95, true,  9,  false, null));
  out.push(rep(PLAYERS.elfandor.id, "elfandor", "Elfandor", n++,107, false, 10, true,  null));

  // Oophies: R1 W 2-1 vs adood, R2 L 1-2 vs samp, R3 L 0-2 vs Noya
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++,  6, true,  8,  true,  1));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 15, false, 13, false, 1));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 24, true,  7,  true,  1));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 50, true,  9,  false, 2));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 59, false, 11, true,  2));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 68, false, 14, false, 2));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++, 92, false, 7,  false, 3));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++,101, false, 13, false, 3));
  out.push(rep(PLAYERS.oophies.id, "oophies", "Oophies", n++,118, true,  8,  true,  null));

  return out;
}
