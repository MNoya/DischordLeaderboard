import { useEffect, useMemo, useState } from "react";

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

export interface DeckUrlRef {
  deckScreenshotUrl: string | null;
  eventId?: string | null;
  displayName: string;
  participantDisplayName?: string | null;
  screenshotChannelId?: string | null;
  screenshotMessageId?: string | null;
}

// Resolves a deck screenshot URL, swapping an expired Discord CDN link for a freshly signed one via
// the refresh edge function. Falls back to the stored URL when refresh isn't possible or fails.
export function useResolvedDeckUrl(ref: DeckUrlRef): { url: string | null; resolving: boolean } {
  const {
    deckScreenshotUrl,
    eventId,
    displayName,
    participantDisplayName,
    screenshotChannelId,
    screenshotMessageId,
  } = ref;
  const canRefresh = !!eventId || (!!screenshotChannelId && !!screenshotMessageId);
  const needsRefresh = useMemo(() => {
    if (!deckScreenshotUrl || !canRefresh) return false;
    return isDiscordCdnUrl(deckScreenshotUrl) && !isDiscordUrlFresh(deckScreenshotUrl);
  }, [deckScreenshotUrl, canRefresh]);

  const [url, setUrl] = useState<string | null>(needsRefresh ? null : deckScreenshotUrl);
  const [resolving, setResolving] = useState(needsRefresh);

  useEffect(() => {
    setUrl(needsRefresh ? null : deckScreenshotUrl);
    setResolving(needsRefresh);
  }, [deckScreenshotUrl, needsRefresh]);

  useEffect(() => {
    if (!needsRefresh) return;
    const lookupName = participantDisplayName ?? displayName;
    const fetchFresh =
      screenshotChannelId && screenshotMessageId
        ? refreshMessageImageUrl(screenshotChannelId, screenshotMessageId)
        : eventId
          ? refreshDeckUrl(eventId, lookupName)
          : Promise.resolve(null);
    let cancelled = false;
    fetchFresh
      .then((fresh) => {
        if (!cancelled) setUrl(fresh ?? deckScreenshotUrl);
      })
      .finally(() => {
        if (!cancelled) setResolving(false);
      });
    return () => {
      cancelled = true;
    };
  }, [needsRefresh, eventId, displayName, participantDisplayName, deckScreenshotUrl, screenshotChannelId, screenshotMessageId]);

  return { url, resolving };
}
