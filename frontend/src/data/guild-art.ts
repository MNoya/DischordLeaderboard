const GUILD_FILENAME: Record<string, string> = {
  WU: "azorius",
  WB: "orzhov",
  WR: "boros",
  WG: "selesnya",
  UB: "dimir",
  UR: "izzet",
  UG: "simic",
  BR: "rakdos",
  BG: "golgari",
  RG: "gruul",
};

const NUDGE_Y_PCT: Record<string, number> = {
  WR: -13,
  RG: -7,
  WU: -10,
  UR: -7,
  WB: -3,
  WG: -7,
};

const BASE = "/leaderboard/guilds";

export function guildSvgUrl(code: string): string | null {
  const guild = GUILD_FILENAME[code];
  return guild ? `${BASE}/${guild}.webp` : null;
}

export function guildLogoTransform(code: string): string | undefined {
  const pct = NUDGE_Y_PCT[code];
  return pct ? `translateY(${pct}%)` : undefined;
}
