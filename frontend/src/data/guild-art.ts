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
  BR: -7,
};

const SCALE_PCT: Record<string, number> = {
  WB: 20,
  RG: 20,
  BR: 20,
};

const BASE = `${import.meta.env.BASE_URL}guilds`;

export function guildSvgUrl(code: string): string | null {
  const guild = GUILD_FILENAME[code];
  return guild ? `${BASE}/${guild}.webp` : null;
}

export function guildLogoTransform(code: string): string | undefined {
  const y = NUDGE_Y_PCT[code] ?? 0;
  const s = SCALE_PCT[code] ?? 0;
  const parts: string[] = [];
  if (y) parts.push(`translateY(${y}%)`);
  if (s) parts.push(`scale(${1 + s / 100})`);
  return parts.length ? parts.join(" ") : undefined;
}

let preloaded = false;
export function preloadGuildLogos(): void {
  if (preloaded || typeof window === "undefined") return;
  preloaded = true;
  for (const name of Object.values(GUILD_FILENAME)) {
    const img = new Image();
    img.src = `${BASE}/${name}.webp`;
  }
}
