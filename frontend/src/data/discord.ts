import { DISCORD_INVITE_CODE } from "./site";

// Live guild headline numbers, fetched browser-direct from Discord's public
// invite API — the same with-counts endpoint Discord's own embeds use. It
// reflects the request Origin, so CORS passes from the site without a proxy.

export interface DiscordStats {
  memberCount: number;
  onlineCount: number;
}

export async function fetchDiscordStats(): Promise<DiscordStats> {
  const url = `https://discord.com/api/v10/invites/${DISCORD_INVITE_CODE}?with_counts=true`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Discord invite API responded ${res.status}`);
  }
  const body = await res.json();
  return {
    memberCount: body.approximate_member_count ?? 0,
    onlineCount: body.approximate_presence_count ?? 0,
  };
}
