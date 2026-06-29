import { supabase } from "./supabase";

const FRESH_WINDOW_MS = 60 * 60 * 1000;

export function isDiscordCdnUrl(url: string): boolean {
  return url.includes("cdn.discordapp.com") || url.includes("media.discordapp.net");
}

export function isDiscordUrlFresh(url: string): boolean {
  try {
    const ex = new URL(url).searchParams.get("ex");
    if (!ex) return false;
    const seconds = parseInt(ex, 16);
    if (!Number.isFinite(seconds)) return false;
    return seconds * 1000 - Date.now() > FRESH_WINDOW_MS;
  } catch {
    return false;
  }
}

interface RefreshResponse {
  url: string | null;
  refreshed: boolean;
}

export async function refreshDeckUrl(
  eventId: string,
  displayName: string,
): Promise<string | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.functions.invoke<RefreshResponse>(
    "refresh-deck-url",
    { body: { eventId, displayName } },
  );
  if (error) {
    console.warn("refresh-deck-url failed", error);
    return null;
  }
  return data?.url ?? null;
}

// Re-resolve any message's first image attachment to a fresh signed URL. Backs self-reported
// trophy screenshots, which carry the channel + message ref instead of a pod event key.
export async function refreshMessageImageUrl(
  channelId: string,
  messageId: string,
): Promise<string | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.functions.invoke<RefreshResponse>(
    "refresh-deck-url",
    { body: { channelId, messageId } },
  );
  if (error) {
    console.warn("refresh-deck-url (message) failed", error);
    return null;
  }
  return data?.url ?? null;
}
