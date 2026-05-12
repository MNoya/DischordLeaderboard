const GUILD_FILENAME: Record<string, string> = {
  WU: "WU",
  WB: "WB",
  WR: "RW",
  WG: "GW",
  UB: "UB",
  UR: "UR",
  UG: "GU",
  BR: "BR",
  BG: "BG",
  RG: "RG",
};

const BASE = "/leaderboard/guild-art";

export function guildSvgUrl(code: string): string | null {
  const guild = GUILD_FILENAME[code];
  return guild ? `${BASE}/${guild}.svg` : null;
}
